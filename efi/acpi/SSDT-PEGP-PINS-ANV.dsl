/*
 * The reset and power-enable pads of the PEG0 slot (the dGPU), for macOS.
 *
 * The firmware declares \_SB.PC00.PEG0.RSTG and PWRG as { Zero, Zero } and fills them from its NVS variables
 * P1RE, P1RP, P1PE and P1PP with four statements that sit outside any method. macOS's ACPI interpreter runs the
 * If blocks it finds outside methods, not bare statements: on macOS both packages stay empty, so \PIN.ON and
 * \PIN.OFF drive pad 0 instead of the card's reset and power-enable pads. \_SB.PC00.PEG0.PXP._OFF then neither
 * resets the card nor cuts its power, and _ON, finding power good still high, returns at once.
 *
 * These are the same four statements inside an If block. Darwin only. Nothing is switched off by this table: it
 * makes the firmware's own power sequences act on the right pads when a driver asks for them.
 */
DefinitionBlock ("", "SSDT", 2, "ACER", "ANVPEGP", 0x00000001)
{
    External (_SB_.PC00.PEG0.RSTG, PkgObj)
    External (_SB_.PC00.PEG0.PWRG, PkgObj)
    External (P1RE, FieldUnitObj)
    External (P1RP, FieldUnitObj)
    External (P1PE, FieldUnitObj)
    External (P1PP, FieldUnitObj)

    If (_OSI ("Darwin"))
    {
        If ((CondRefOf (\_SB.PC00.PEG0.RSTG) && CondRefOf (\_SB.PC00.PEG0.PWRG)))
        {
            If ((CondRefOf (P1RE) && CondRefOf (P1PE)))
            {
                \_SB.PC00.PEG0.RSTG [Zero] = P1RE
                \_SB.PC00.PEG0.RSTG [One] = P1RP
                \_SB.PC00.PEG0.PWRG [Zero] = P1PE
                \_SB.PC00.PEG0.PWRG [One] = P1PP
            }
        }
    }
}
