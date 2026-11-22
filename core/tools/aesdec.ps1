param(
  [Parameter(Mandatory)][string]$KeyHex,
  [Parameter(Mandatory)][ValidateSet('ECB', 'CBC')][string]$Mode,
  [Parameter(Mandatory)][string]$InFile,
  [Parameter(Mandatory)][string]$OutFile
)
# AES-128 decrypt without padding (zero IV for CBC), as XEX2 uses it.
$key = [byte[]]::new($KeyHex.Length / 2)
for ($i = 0; $i -lt $key.Length; $i++) { $key[$i] = [Convert]::ToByte($KeyHex.Substring($i * 2, 2), 16) }
$aes = [System.Security.Cryptography.Aes]::Create()
$aes.Key = $key
$aes.IV = [byte[]]::new(16)
$aes.Padding = [System.Security.Cryptography.PaddingMode]::None
$aes.Mode = if ($Mode -eq 'ECB') { [System.Security.Cryptography.CipherMode]::ECB } else { [System.Security.Cryptography.CipherMode]::CBC }
$data = [System.IO.File]::ReadAllBytes($InFile)
$dec = $aes.CreateDecryptor().TransformFinalBlock($data, 0, $data.Length)
[System.IO.File]::WriteAllBytes($OutFile, $dec)
