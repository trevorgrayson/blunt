# apt install texlive-latex-base texlive-latex-recommended texlive-fonts-recommended pandoc 

echo $1
pandoc $1 --toc -o $1.pdf

