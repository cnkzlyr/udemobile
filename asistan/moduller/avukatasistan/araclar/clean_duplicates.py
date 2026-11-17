#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TickTick Akıllı Mükerrer Temizleme ve Ek Koruma Scripti (v8.0)
Tüm projelerdeki ve Inbox'taki mükerrerleri temizler, elle girilmiş notları korur ve birleştirir.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # proje kökü
from ticktick_sync import clean_and_merge_duplicates, clean_completed_duplicates

if __name__ == "__main__":
    clean_and_merge_duplicates()
    clean_completed_duplicates()
