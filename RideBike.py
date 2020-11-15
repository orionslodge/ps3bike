#!/usr/bin/python3

import ps3bike

try:
	bike = ps3bike.PS3Bike()
except Exception as e:
	print(e)
	exit(1)

bike.start_controller ()
