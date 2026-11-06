// Conditional legacy RTC selection. Source DSDT must be checked before boot.
// Reference: OpenCore SSDT-AWAC-DISABLE and Dortania SSDT-AWAC.
DefinitionBlock ("", "SSDT", 2, "ACER", "ANVAWAC", 0x00000001)
{
    External (STAS, IntObj)
    If (_OSI ("Darwin"))
    {
        If (CondRefOf (STAS)) { STAS = One }
    }
}
