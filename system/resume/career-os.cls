\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{career-os}[2026/07/22 Career OS legacy-calibrated resume class]
\LoadClass[11pt]{article}

\setlength{\parindent}{0pt}
\RequirePackage{xltxtra}
\RequirePackage{xifthen}
\RequirePackage[dvipsnames]{xcolor}
\RequirePackage{hyperref}
\hypersetup{
  colorlinks=true,
  linkcolor=black,
  filecolor=black,
  urlcolor=MidnightBlue,
  citecolor=black,
  unicode=true
}
\RequirePackage{url}
\urlstyle{same}
\RequirePackage{fontspec}

\providecommand{\CareerOSLatinBodyFontPath}{}
\providecommand{\CareerOSLatinBodyRegularFont}{texgyretermes-regular.otf}
\providecommand{\CareerOSLatinBodyBoldFont}{texgyretermes-bold.otf}
\providecommand{\CareerOSLatinBodyItalicFont}{texgyretermes-italic.otf}
\providecommand{\CareerOSLatinBodyBoldItalicFont}{texgyretermes-bolditalic.otf}
\providecommand{\CareerOSLatinDisplayFontPath}{}
\providecommand{\CareerOSLatinDisplayRegularFont}{texgyreheros-regular.otf}
\providecommand{\CareerOSLatinDisplayBoldFont}{texgyreheros-bold.otf}
\providecommand{\CareerOSLatinDisplayItalicFont}{texgyreheros-italic.otf}
\providecommand{\CareerOSLatinDisplayBoldItalicFont}{texgyreheros-bolditalic.otf}
\providecommand{\CareerOSCJKBodyFontPath}{}
\providecommand{\CareerOSCJKBodyRegularFont}{SourceHanSerifSC-Regular.otf}
\providecommand{\CareerOSCJKBodyBoldFont}{SourceHanSerifSC-Bold.otf}
\providecommand{\CareerOSCJKBodyItalicFont}{SourceHanSerifSC-Regular.otf}
\providecommand{\CareerOSCJKBodyBoldItalicFont}{SourceHanSerifSC-Bold.otf}
\providecommand{\CareerOSCJKDisplayFontPath}{}
\providecommand{\CareerOSCJKDisplayRegularFont}{NotoSansCJKsc-Regular.otf}
\providecommand{\CareerOSCJKDisplayBoldFont}{NotoSansCJKsc-Bold.otf}
\providecommand{\CareerOSCJKDisplayItalicFont}{NotoSansCJKsc-Regular.otf}
\providecommand{\CareerOSCJKDisplayBoldItalicFont}{NotoSansCJKsc-Bold.otf}
\providecommand{\CareerOSCJKMonoFontPath}{}
\providecommand{\CareerOSCJKMonoRegularFont}{NotoSansCJKsc-Regular.otf}
\providecommand{\CareerOSCJKMonoBoldFont}{NotoSansCJKsc-Bold.otf}
\providecommand{\CareerOSCJKMonoItalicFont}{NotoSansCJKsc-Regular.otf}
\providecommand{\CareerOSCJKMonoBoldItalicFont}{NotoSansCJKsc-Bold.otf}

% Materialize configurable filenames before fontspec 2.8 parses its keys.
\edef\CareerOSSetMainFont{%
  \noexpand\setmainfont{\CareerOSLatinBodyRegularFont}[
    BoldFont=\CareerOSLatinBodyBoldFont,
    ItalicFont=\CareerOSLatinBodyItalicFont,
    BoldItalicFont=\CareerOSLatinBodyBoldItalicFont
  ]%
}
\CareerOSSetMainFont
\edef\CareerOSSetSansFont{%
  \noexpand\setsansfont{\CareerOSLatinDisplayRegularFont}[
    BoldFont=\CareerOSLatinDisplayBoldFont,
    ItalicFont=\CareerOSLatinDisplayItalicFont,
    BoldItalicFont=\CareerOSLatinDisplayBoldItalicFont
  ]%
}
\CareerOSSetSansFont

\RequirePackage{xeCJK}
\edef\CareerOSSetCJKMainFont{%
  \noexpand\setCJKmainfont{\CareerOSCJKBodyRegularFont}[
    BoldFont=\CareerOSCJKBodyBoldFont,
    ItalicFont=\CareerOSCJKBodyItalicFont,
    BoldItalicFont=\CareerOSCJKBodyBoldItalicFont
  ]%
}
\CareerOSSetCJKMainFont
\edef\CareerOSSetCJKSansFont{%
  \noexpand\setCJKsansfont{\CareerOSCJKDisplayRegularFont}[
    BoldFont=\CareerOSCJKDisplayBoldFont,
    ItalicFont=\CareerOSCJKDisplayItalicFont,
    BoldItalicFont=\CareerOSCJKDisplayBoldItalicFont
  ]%
}
\CareerOSSetCJKSansFont
\edef\CareerOSSetCJKMonoFont{%
  \noexpand\setCJKmonofont{\CareerOSCJKMonoRegularFont}[
    BoldFont=\CareerOSCJKMonoBoldFont,
    ItalicFont=\CareerOSCJKMonoItalicFont,
    BoldItalicFont=\CareerOSCJKMonoBoldItalicFont
  ]%
}
\CareerOSSetCJKMonoFont

\RequirePackage[
  a4paper,
  left=0.75in,
  right=0.75in,
  top=0.65in,
  bottom=0.55in,
  nohead
]{geometry}

\RequirePackage{titlesec}
\RequirePackage{enumitem}
\setlist{noitemsep}
\setlist[itemize]{topsep=0.2em, partopsep=0pt, leftmargin=1.5em, itemsep=0.1em}
\setlist[enumerate]{topsep=0.2em, partopsep=0pt, leftmargin=1.5em, itemsep=0.1em}
\RequirePackage[super]{nth}
\RequirePackage{linespacing_fix}
\linespread{1.25}

\titleformat{\section}
{\Large\sffamily\bfseries\raggedright}
{}{0em}
{}
[{\color{black!35}\titlerule[0.6pt]}]
\titlespacing*{\section}{0cm}{*1.8}{*1.2}

\titleformat{\subsection}
{\large\sffamily\bfseries\raggedright}
{}{0em}
{}
\titlespacing*{\subsection}{0cm}{*1.5}{*0.6}

\newcommand{\jobsection}[4]{%
  \section[#1 | #2 #3]{%
    {\Large\bfseries #1}
      {\color{black!60}\ |\ }
      {\small\fontseries{m}\selectfont\color{black!65} #2}
    \hspace{1.2em}
    {\normalsize\fontseries{m}\selectfont #3}
    \hfill
    {\normalfont\sffamily\normalsize\color{black!70} #4}
  }%
}

\newcommand{\projectsection}[3]{%
  \subsection[#1, #2]{%
    {\large\bfseries #1}
    \hspace{1em}
    {\normalfont\sffamily\normalsize\color{black!70} #2}
    \hfill
    {\normalfont\sffamily\normalsize\color{black!70} #3}
  }%
}

\newcommand{\edusection}[4]{%
  \subsection[#1 #2 #3]{%
    {\bfseries #1}
    \hspace{0.5em}
    {\normalfont\sffamily\normalsize\color{black!70}#2\quad #3}
    \hfill
    {\normalfont\sffamily\normalsize\color{black!70} #4}
  }%
}

\newcommand{\skillitem}[2]{{\sffamily\bfseries #1}\quad {\color{black!75}#2}}
\newcommand{\skilldot}{{\color{black!40}\ $\bullet$\ }}
\newcommand{\contactlabel}[1]{{\sffamily\bfseries\color{black!70}#1}}
\newcommand{\resumebullet}[2]{\item {\sffamily\bfseries #1}: #2}
\newcommand{\CareerClaim}[2]{#2}
\newcommand{\CareerClaims}[2]{#2}

\RequirePackage{career-os-style}
\endinput
