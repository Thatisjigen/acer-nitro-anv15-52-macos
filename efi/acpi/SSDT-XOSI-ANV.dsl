// Adapts the Windows compatibility list from the supplied AN515-57
// XOSI table. Only the Acer OEM DSDT is patched; these _OSI calls stay native.
// Other operating systems continue to boot directly through rEFInd.
DefinitionBlock ("", "SSDT", 2, "ACER", "ANVXOSI", 0x00000001)
{
    If (_OSI ("Darwin"))
    {
        Method (XOSI, 1, NotSerialized)
        {
            Local0 = Package (0x10)
            {
                "Windows 2000",
                "Windows 2001",
                "Windows 2001 SP1",
                "Windows 2001.1",
                "Windows 2001 SP2",
                "Windows 2001.1 SP1",
                "Windows 2006",
                "Windows 2006 SP1",
                "Windows 2006.1",
                "Windows 2009",
                "Windows 2012",
                "Windows 2013",
                "Windows 2015",
                "Windows 2016",
                "Windows 2017",
                "Windows 2017.2"
            }
            Return (Match (Local0, MEQ, Arg0, MTR, Zero, Zero) != Ones)
        }
    }
}
