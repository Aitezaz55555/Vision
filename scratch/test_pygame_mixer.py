import sys
import os
import time
import threading

# Verify pygame mixer stop
try:
    import pygame
    pygame.mixer.init()
    print("Pygame mixer initialized successfully")
except Exception as e:
    print("Pygame mixer error:", e)
