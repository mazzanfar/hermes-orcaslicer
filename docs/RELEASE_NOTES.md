# 0.5.0

Security fix for the Hermes catalog review: credential names must use the ORCA_ or HERMES_ORCA_ namespace, and credential-bearing printer/camera requests require HTTPS unless plaintext is explicitly enabled. Enforcement also applies to saved connections and credential reads.

Upgrade from 0.4.0 or earlier. Legacy connections may fail closed; see [migration](CONNECTIONS.md#credentials-and-migration). Never repurpose provider secrets as printer credentials. The plaintext opt-in records configuration intent, not independent human authorization.

Wheel, source archive and SHA-256 checksums accompany the release. Slicing and protocol capabilities are unchanged; no new physical hardware certification is claimed. See [changelog](../CHANGELOG.md) and [validation](VALIDATION.md).
