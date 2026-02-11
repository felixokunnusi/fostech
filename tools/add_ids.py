import pandas as pd
import os

FILES = [
    ("psr_2021_confirmation_all_typed.csv", "CONFIRMATION"),
    ("psr_2021_grade_1_4_all_typed.csv", "GRADE_1_4"),
    ("psr_2021_grade_5_7_all_typed.csv", "GRADE_5_7"),
    ("psr_2021_grade_8_10_master_200_typed.csv", "GRADE_8_10"),
    ("psr_2021_grade_12_14_master_200_typed.csv", "GRADE_12_14"),
    ("psr_2021_grade_15_16_master_200_typed.csv", "GRADE_15_16"),
    ("psr_2021_grade_17_master_200_typed.csv", "GRADE_17"),
]

for filename, bank in FILES:

    if not os.path.exists(filename):
        print(f"Skipping {filename} (not found)")
        continue

    df = pd.read_csv(filename)

    df.insert(
        0,
        "question_id",
        [
            f"PSR2021-{bank}-{str(i+1).zfill(5)}"
            for i in range(len(df))
        ],
    )

    new_name = filename.replace(".csv", "_with_ids.csv")
    df.to_csv(new_name, index=False)

    print(f"✅ {new_name} created ({len(df)} questions)")
