param(
    [string]$Python = "",
    [switch]$ChinaMirror,
    [string]$GitHubMirror = ""
)

$Root = Split-Path -Parent $PSScriptRoot
$ThirdParty = Join-Path $Root "third_party"
$Repo = Join-Path $ThirdParty "Seed-VC"
$Venv = Join-Path $ThirdParty "seedvc-venv"
$VenvPython = Join-Path $Venv "Scripts\python.exe"

function Fail($Message) {
    Write-Host ""
    Write-Host "ERROR: $Message" -ForegroundColor Red
    exit 1
}

Write-Host "[1/5] Preparing third_party directory..."
New-Item -ItemType Directory -Force -Path $ThirdParty | Out-Null

Write-Host "[2/5] Cloning Seed-VC (if needed)..."
if (-not (Test-Path (Join-Path $Repo "inference.py"))) {
    if (Test-Path $Repo) {
        Write-Host "      Removing incomplete Seed-VC checkout..."
        Remove-Item -Recurse -Force $Repo
    }
    $RepoUrl = "https://github.com/Plachtaa/Seed-VC.git"
    if ($GitHubMirror -ne "") {
        $RepoUrl = "$GitHubMirror/$RepoUrl"
    }
    git clone $RepoUrl $Repo
    if ($LASTEXITCODE -ne 0) { Fail "git clone failed." }
} else {
    Write-Host "      Seed-VC already present, skipping clone."
}

Write-Host "[3/5] Pulling Git LFS assets (example audios)..."
git -C $Repo lfs install | Out-Null
git -C $Repo lfs pull
if ($LASTEXITCODE -ne 0) { Fail "git lfs pull failed." }

if ($Python -eq "") {
    $Python = "python"
}

Write-Host "[4/5] Creating virtualenv at $Venv ..."
if (-not (Test-Path $VenvPython)) {
    & $Python -m venv $Venv
    if ($LASTEXITCODE -ne 0) { Fail "venv creation failed." }
}
& $VenvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { Fail "pip upgrade failed." }

Write-Host "[5/5] Installing Seed-VC dependencies..."
$PipIndex = @()
if ($ChinaMirror) {
    $PipIndex = @("-i", "https://pypi.tuna.tsinghua.edu.cn/simple")
}

# The Windows CUDA wheel for torch 2.4.0 exists, but the matching
# torchaudio 2.4.0+cu121 Windows wheel does NOT exist (torchaudio's Windows
# CUDA builds stop at 2.3.1).  So we install the last fully-matching CUDA
# trio instead:
#   torch 2.3.1+cu121 / torchvision 0.18.1+cu121 / torchaudio 2.3.1+cu121
# All three Windows (Python 3.11) wheels were verified to exist on the
# official download.pytorch.org index and on the SJTU cu121 mirror.
Write-Host "      Removing any previously mis-installed (e.g. CPU) PyTorch..."
& $VenvPython -m pip uninstall -y torch torchaudio torchvision 2>&1 | Out-Null

$TorchSpecs = @(
    "torch==2.3.1+cu121",
    "torchvision==0.18.1+cu121",
    "torchaudio==2.3.1+cu121"
)
$TorchInstalled = $false

if ($ChinaMirror) {
    # Download the ~2.5GB torch wheel with curl instead of pip, because curl
    # can resume an interrupted download (-C -) while pip restarts from zero.
    # This avoids the "SSL: DECRYPTION_FAILED_OR_BAD_RECORD_MAC" failures that
    # happen when a flaky connection drops mid-download.
    Write-Host "      Downloading PyTorch 2.3.1+cu121 wheels (resumable, ~2.5GB total)..." -ForegroundColor Yellow
    Write-Host "      If it is interrupted, just re-run this script and it will continue from where it stopped." -ForegroundColor Yellow
    $DlDir = Join-Path $ThirdParty "seedvc-wheels"
    New-Item -ItemType Directory -Force -Path $DlDir | Out-Null
    $Base = "https://mirrors.sjtug.sjtu.edu.cn/pytorch-wheels/cu121"
    $WheelFiles = @(
        "torch-2.3.1+cu121-cp311-cp311-win_amd64.whl",
        "torchvision-0.18.1+cu121-cp311-cp311-win_amd64.whl",
        "torchaudio-2.3.1+cu121-cp311-cp311-win_amd64.whl"
    )
    foreach ($f in $WheelFiles) {
        $url = "$Base/$f"
        $dest = Join-Path $DlDir $f
        Write-Host "      Downloading $f ..."
        & curl.exe -L -C - --retry 30 --retry-delay 3 --retry-all-errors -o $dest $url
        if ($LASTEXITCODE -ne 0) { Fail "download failed for $f" }
    }
    Write-Host "      Installing the downloaded wheels locally..."
    $wheelPaths = $WheelFiles | ForEach-Object { Join-Path $DlDir $_ }
    & $VenvPython -m pip install --no-deps @wheelPaths -i "https://pypi.tuna.tsinghua.edu.cn/simple"
    if ($LASTEXITCODE -ne 0) { Fail "local wheel install failed." }
    & $VenvPython -m pip install filelock typing-extensions sympy networkx jinja2 fsspec pillow -i "https://pypi.tuna.tsinghua.edu.cn/simple"
    if ($LASTEXITCODE -ne 0) { Fail "torch runtime dependencies install failed." }
    $TorchInstalled = $true
} else {
    Write-Host "      Installing PyTorch 2.3.1+cu121 (this is the big download)..."
    & $VenvPython -m pip install @TorchSpecs `
        --extra-index-url "https://download.pytorch.org/whl/cu121" `
        --retries 10 --timeout 60
    if ($LASTEXITCODE -eq 0) { $TorchInstalled = $true }
}

if (-not $TorchInstalled) { Fail "PyTorch install failed." }

Write-Host "      Installing offline-inference dependencies..."
& $VenvPython -m pip install -r (Join-Path $PSScriptRoot "seedvc_inference_requirements.txt") @PipIndex
if ($LASTEXITCODE -ne 0) { Fail "inference dependencies install failed." }

Write-Host "      Verifying install..."
$verify = & $VenvPython -c "import torch, torchaudio, torchvision, librosa, transformers, pydub, munch, onnxruntime, dac, tqdm; print('torch', torch.__version__, 'cuda', torch.cuda.is_available(), 'torchaudio', torchaudio.__version__)" 2>&1
$verify | ForEach-Object { Write-Host $_ }
if ($LASTEXITCODE -ne 0) { Fail "verification failed: some dependencies could not be imported." }

$cudaOk = & $VenvPython -c "import torch; print(torch.cuda.is_available())"
if ($cudaOk -eq "True") {
    Write-Host "      CUDA is available. GPU inference is ready." -ForegroundColor Green
} else {
    Write-Host "      WARNING: CUDA is not available. PyTorch will fall back to CPU (slow)." -ForegroundColor Yellow
    Write-Host "      Check that your NVIDIA driver is installed and up to date." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Setup complete."
Write-Host "  Seed-VC repo : $Repo"
Write-Host "  Virtualenv   : $VenvPython"
Write-Host ""
Write-Host "If you are in China and the first inference cannot download weights,"
Write-Host "set the HuggingFace mirror before starting the backend:"
Write-Host "  `$env:SEEDVC_HF_ENDPOINT = 'https://hf-mirror.com'"
Write-Host ""
Write-Host "Then restart the backend and select the neural voice mode in the UI."
