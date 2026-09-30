# Manzanita v31 Windows-native runtime qualification

This bounded object executes the exact v31 Python runtime resolver and its process-local `py`, `python`, and `python3` compatibility shims on a GitHub-hosted Windows runner. It exists to close the unobserved Windows PowerShell and runtime-resolution campaign left by the local bootstrap qualification.

The campaign does not search an operator workstation, export a File Library object, materialize a production input, invoke the v31 admission mechanism, extract the accepted parent, mutate a product surface, merge, release, deploy Pages, or create an external effect. A passing result proves only that the resolver and aliases operate under the recorded Windows runner and PowerShell environments.

The workflow parses the PowerShell sources with both Windows PowerShell 5.1 and PowerShell 7, verifies the bounded source contract, executes the exact `.cmd` launcher, validates the resulting machine receipt, and retains that receipt as an Actions artifact.
