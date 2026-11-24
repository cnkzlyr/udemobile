$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
python "$scriptDir\drive_arsiv_denetle.py" $args
