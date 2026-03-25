# fix_calibrator.py
from train_calibration import train_isotonic_calibrator
import os

if __name__ == "__main__":
    print("🔄 Iniciando re-entrenamiento nativo del calibrador...")
    train_isotonic_calibrator()
    print("✅ Proceso terminado.")