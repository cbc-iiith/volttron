
# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright (c) 2020, Sam Babu, Godithi.
# All rights reserved.
#
#
# IIIT Hyderabad

#}}}

#Sam

import sys

from ispace_utils import Runningstats

rc = Runningstats(120)
# D:\Sam NotExtreme\FDD_LAB_VOLT_LOGS\Analysis\Book2.xlsx Sheet3
rc.push(1086.84)
rc.push(1084.39)
rc.push(1101.76)
rc.push(1118.71)
rc.push(1175.62)
rc.push(1193.5)
rc.push(1867.3)
rc.push(4643.15)
rc.push(9567.53)
rc.push(10749.04)
rc.push(13744.6)
rc.push(13988.82)
rc.push(18398.27)
rc.push(15668.12)
rc.push(16422.07)
rc.push(14924.56)
rc.push(13230.41)
rc.push(13364.36)
rc.push(13061.1)
rc.push(12591.44)
rc.push(12354.83)
rc.push(12338.71)
rc.push(12240.55)
rc.push(11936.28)
rc.push(11736.06)
rc.push(11701.95)
rc.push(11570.09)
rc.push(11496.75)
rc.push(11342.42)
rc.push(11529.91)
rc.push(11298.79)
rc.push(11327.1)
rc.push(11027.94)
rc.push(11139.8)
rc.push(10954.59)
rc.push(11427.72)
rc.push(10975.83)
rc.push(10927.54)
rc.push(10942.3)
rc.push(10924.17)
rc.push(10788.68)
rc.push(10836.77)
rc.push(10784.29)
rc.push(10837.6)
rc.push(10827.91)
rc.push(10930.52)
rc.push(10973.06)
rc.push(10749.2)
rc.push(10852.98)
rc.push(10879.52)
rc.push(10733.53)
rc.push(10792.81)
rc.push(10795.36)
rc.push(10764.67)
rc.push(10546.55)
rc.push(10734.5)
rc.push(10456.08)
rc.push(10463.81)
rc.push(10458.25)
rc.push(10542.76)
rc.push(10644.25)
rc.push(10601.24)
rc.push(10658.99)
rc.push(10621.82)
rc.push(10553.45)
rc.push(10614.37)
rc.push(10623.51)
rc.push(10578.18)
rc.push(10797.12)
rc.push(10597.52)
rc.push(10603.52)
rc.push(10509.29)
rc.push(10444.47)
rc.push(10084.96)
rc.push(10092.79)
rc.push(9843.67)
rc.push(9124.42)
rc.push(9000.31)
rc.push(8743.19)
rc.push(8183.78)
rc.push(7768.95)
rc.push(7456.12)
rc.push(6696.11)
rc.push(6202.96)
rc.push(5954.66)
rc.push(5712.57)
rc.push(5724.01)
rc.push(5703.67)
rc.push(5650.99)
rc.push(5485.79)
rc.push(5447.47)
rc.push(5688.41)
rc.push(5493.75)
rc.push(5557.53)
rc.push(5566.5)
rc.push(5588.97)
rc.push(5449.55)
rc.push(5676.86)
rc.push(5526.98)
rc.push(5290.42)
rc.push(5247.72)
rc.push(5411.22)
rc.push(5409.84)
rc.push(5688.5)
rc.push(5913.69)
rc.push(6084.98)
rc.push(6205.03)
rc.push(6426.22)
rc.push(6536.86)
rc.push(6800.36)
rc.push(6685.43)
rc.push(6659.51)
rc.push(6660.71)
rc.push(6803.4)
rc.push(6863.27)
rc.push(6725.03)
rc.push(6844.59)
rc.push(6884.42)
rc.push(6991.08)
rc.push(7045.36)

print('count: {}'.format(rc.num_data_values()))
print('mean: {}'.format(rc.mean()))
print('variance: {}'.format(rc.variance()))
print('std_dev: {}'.format(rc.std_dev()))
print('skewness: {}'.format(rc.skewness()))
print('kurtosis: {}'.format(rc.kurtosis()))
print('exp_wt_mv_avg: {}'.format(rc.exp_wt_mv_avg()))
