param(
    [string]$ConfigDir = (Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'PROSPECTOR/EntregaFinal'),
    [string]$Python = 'python',
    [string]$OpenSSL = 'openssl',
    [switch]$Start
)

$ErrorActionPreference = 'Stop'
$env:Path = "$env:WINDIR\System32;$env:Path"
$repo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$utf8 = [Text.UTF8Encoding]::new($false)
function Assert-Native([string]$Action) {
    if ($LASTEXITCODE -ne 0) { throw "$Action failed ($LASTEXITCODE)" }
}

Push-Location $repo
try {
    $null = New-Item -ItemType Directory -Path $ConfigDir -Force
    $ConfigDir = (Resolve-Path -LiteralPath $ConfigDir).Path
    $owner = [Security.Principal.WindowsIdentity]::GetCurrent().Name
    & icacls.exe $ConfigDir /inheritance:r /grant:r "${owner}:(OI)(CI)F" | Out-Null
    Assert-Native 'Protecting the configuration directory'
    $random = [Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        foreach ($name in 'service_key','assertion_key','metadata_key','callback_key') {
            $file = Join-Path $ConfigDir $name
            if (!(Test-Path -LiteralPath $file)) {
                $bytes = New-Object byte[] 48
                $random.GetBytes($bytes)
                [IO.File]::WriteAllText($file, [Convert]::ToBase64String($bytes), $utf8)
            }
        }
    } finally { $random.Dispose() }

    $cert = Join-Path $ConfigDir 'tls_crt'
    $key = Join-Path $ConfigDir 'tls_key'
    if (!(Test-Path -LiteralPath $cert) -and !(Test-Path -LiteralPath $key)) {
        $conf = Join-Path $ConfigDir 'openssl.cnf'
        [IO.File]::WriteAllLines($conf, [string[]]@('[req]','distinguished_name=dn','[dn]'), $utf8)
        & $OpenSSL req -config $conf -x509 -newkey rsa:2048 -nodes -days 7 -subj /CN=localhost -addext subjectAltName=DNS:localhost,IP:127.0.0.1 -addext extendedKeyUsage=serverAuth -out $cert -keyout $key
        Assert-Native 'Generating the local TLS certificate'
    }
    if (!(Test-Path -LiteralPath $cert) -or !(Test-Path -LiteralPath $key)) { throw 'The existing TLS pair is incomplete' }
    & $OpenSSL x509 -in $cert -noout -checkip 127.0.0.1 -checkend 3600
    Assert-Native 'Checking the local TLS certificate'

    $acl = Join-Path $ConfigDir 'platform-allow.conf'
    if (!(Test-Path -LiteralPath $acl)) {
        [IO.File]::WriteAllLines($acl, [string[]]@('allow 127.0.0.1;','allow ::1;'), $utf8)
    }
    $profile = Join-Path $ConfigDir 'seccomp.json'
    if (!(Test-Path -LiteralPath $profile)) {
        & $Python -m scripts.service_seccomp_profile $profile
        Assert-Native 'Generating secured Chromium seccomp'
    }
    & $Python -m scripts.service_seccomp_profile $profile --check
    Assert-Native 'Verifying the SEC-003 fingerprint'
    $path = $ConfigDir.Replace('\','/')
    $envFile = Join-Path $ConfigDir 'service.env'
    if (!(Test-Path -LiteralPath $envFile)) {
        [IO.File]::WriteAllLines($envFile, [string[]]@(
            'SERVICE_IMAGE=prospector-service:entrega-final',
            'NGINX_IMAGE=nginxinc/nginx-unprivileged@sha256:7377697a821c131a924a7105fafbe7414db4e9fcc77a6f08f776f33f141ec3f8',
            'LISTEN_IP=127.0.0.1', 'HTTPS_PORT=8443', 'MAX_ACTIVE_BATCHES=1',
            'SOLUTION_ID=prospector-academic-local', 'ASSERTION_ISSUER=prospector-platform',
            'ASSERTION_AUDIENCE=prospector-service/v1',
            'PLATFORM_CALLBACK_ORIGIN=https://saas-platform-backend-l55n.onrender.com',
            "PLATFORM_ALLOWLIST_FILE='$path/platform-allow.conf'", "PROSPECTOR_SECCOMP_PROFILE='$path/seccomp.json'",
            "SERVICE_API_KEY_FILE='$path/service_key'", "PLATFORM_ASSERTION_KEY_FILE='$path/assertion_key'",
            "SQLITE_HMAC_KEY_FILE='$path/metadata_key'", "CALLBACK_API_KEY_FILE='$path/callback_key'",
            "TLS_CERT_FILE='$path/tls_crt'", "TLS_KEY_FILE='$path/tls_key'"
        ), $utf8)
    }
    $compose = @('compose','--env-file',$envFile,'-p','prospector-final-local',
        '-f','compose.yaml','-f','deploy/gcp/compose.seccomp-candidate.yaml','-f','deploy/local/compose.offline.yaml')
    & docker @compose config --quiet
    Assert-Native 'Validating effective Compose configuration'
    if (!$Start) { return }

    $resources = (& docker info --format '{{.MemTotal}} {{.NCPU}}').Split(' ')
    Assert-Native 'Reading Docker resources'
    if ([int64]$resources[0] -lt 6GB -or [int]$resources[1] -lt 4) {
        throw 'Docker needs at least 6 GiB and 4 CPUs to start the 4 GiB Service safely'
    }
    $image = 'prospector-service:entrega-final'
    & docker image inspect $image --format '{{.Id}}'
    Assert-Native 'Checking the final image'
    foreach ($item in @(
        @{ volume='prospector-final-service-credentials'; uid=10001; files=@('service_key','assertion_key','metadata_key','callback_key') },
        @{ volume='prospector-final-nginx-credentials'; uid=101; files=@('tls_crt','tls_key') }
    )) {
        & docker volume create $item.volume | Out-Null
        Assert-Native 'Preparing the credential volume'
        $names = $item.files -join ' '
        $uid = $item.uid
        $copy = 'set -eu; for item in {0}; do if test -e "/secure/$item"; then cmp -s "/incoming/$item" "/secure/$item"; else install -m 0400 -o {1} -g {1} "/incoming/$item" /secure; fi; done; chown {1}:{1} /secure; chmod 0700 /secure' -f $names,$uid
        & docker run --rm --network none --read-only --user 0 --cap-drop ALL --cap-add CHOWN --cap-add DAC_OVERRIDE --cap-add FOWNER --security-opt no-new-privileges --mount "type=bind,source=$ConfigDir,target=/incoming,readonly" --mount "type=volume,source=$($item.volume),target=/secure" --entrypoint sh $image -c $copy
        Assert-Native 'Checking or provisioning unchanged credentials'
    }
    & docker @compose up -d --no-build --wait
    Assert-Native 'Starting the local stack'
    & docker @compose ps
    Assert-Native 'Checking the local stack'
} finally { Pop-Location }
