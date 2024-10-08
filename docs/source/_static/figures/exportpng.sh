#!/bin/bash

for f in `ls ./*.drawio`; do
	drawio -x $f -o $f.png;
done

