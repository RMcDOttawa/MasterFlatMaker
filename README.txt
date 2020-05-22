This program combines Flat Frames into a master flat.  If run without parameters, a GUI
window opens.  If run given a list of file names as args, then those are immediately processed
without the UI interaction.

	Video introduction and tutorial:  https://www.youtube.com/watch?v=Rj6V3quA_2Q

Files with same dimensions can be manually selected for combination, or you can point the program
to a large set of files and have it automatically group them by dimensions, filter, and temperature
and produce a master flat for each of the grouped sets.

Preferences control how they are combined and where the result goes. You should always run the
GUI version first, even if you intend to use the command line version, and use the Preferences
window to establish some of the behaviours that will happen when the command line is used.

Command line form:
MasterFlatMaker --option --option ...   <list of FITs files>
Options
    -g   or --gui               Force gui interface even though command line used

    Precalibration options: if none given, uses what is set in GUI preferences
    -np  or --noprecal              No precalibration of input files
    -p   or --pedestal <n>          Precalibrate by subtracting pedestal value <n>
    -b   or --bias <p>   			Use the given calibration bias file
    -a   or --auto <dir>            Precalibrate by with best bias file in given directory
    -ar  or --autorecursive         Recursively include sub-directories in auto bias file search
    -ab  or --autobias              Limit auto-selected files to Bias files only
    -ax  or --autoresults           Display specifications of each selected calibration file

    Combination algorithm:  if none, uses GUI preferences
    -m   or --mean                  Combine files with simple mean
    -n   or --median                Combine files with simple median
    -mm  or --minmax <n>            Min-max clipping of <n> values, then mean
    -s   or --sigma <n>             Sigma clipping values greater than z-score <n> then mean

    -v   or --moveinputs <dir>      After successful processing, move input files to directory

    -t   or --ignoretype            Ignore the internal FITS file type (flat, bias, etc)
    
    -o   or --output <path>		    Output file to this location (default: with input files,
                                    used only if no "group" options are chosen)

    -gs  or --groupsize             Group files by size (dimensions and binning)
    -gf  or --groupfilter           Group files by filter name
    -gt  or --grouptemperature <w>  Group files by temperature, with given bandwidth
    -mg  or --minimumgroup <n>      Ignore groups with fewer than <n> files
    -od  or --outputdirectory <d>   Directory to receive grouped master files

Examples:

MasterFlatMaker --noprecal *.fits
MasterFlatMaker -p 100 -s 2.0 *.fits
MasterFlatMaker -a ./bias-library -ar -s 2.0 -gs -gt 10 -od ./output-directory ./data/*.fits
