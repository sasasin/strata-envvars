# `MMVQ_IL_ONLY`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA の開発・診断用実行ファイル `mmvq_il_parity` が実行するテストケースを、ケース名に含まれる文字列で絞る。通常の Strata engine やサーバーの処理を切り替える設定ではない。この実行ファイルは `STRATA_ENABLE_CUDA` のときだけ `strata_gpu_engine.cmake` で定義・CTest 登録される。`MMVQ_IL_ONLY` はケースを選ぶだけで、テーブル検査 `check_tables()` はケース選択より先に常に行われる。ケース一覧は `mmvq_il_parity.cpp` の `CASES` にある。（`engine/cmake/strata_gpu_engine.cmake:813-821`、`engine/src/kernels/mmvq_il_parity.cpp:103-143,509-526`）

## 値と判定

`main()` 内で `std::getenv("MMVQ_IL_ONLY")` により一度読み、各ケース名 `c.name` に対して `std::strstr(c.name, only)` を評価する。未設定（null pointer）なら全ケースを実行し、設定されていれば値全体を大文字小文字を区別する部分文字列として使う。数値や真偽値への変換、空白除去、妥当性検査はない。空文字列はすべてのケース名に一致する。部分一致しない値ならケース本体は一つも実行されない。たとえば `Q5_K` はその文字列を含むケースだけを選び、`true` や `no-such-case` は現在のケース名に一致しない。`0` は数値 0 として扱われず、寸法に `0` を含むケース名に一致する。（`engine/src/kernels/mmvq_il_parity.cpp:108-143,521-524`）

| 条件 | unset | 選択される例 | 一致しない例 |
|---|---|---|---|
| `mmvq_il_parity` の実行 | 全 `CASES` | `Q5_K`、`2560x512` | 空欄（空文字は全ケースに一致） |
| `mmvq_il_parity` の実行 | — | — | `true`、`no-such-case`（現在のケース名に含まれない場合） |

## 有効になる条件

- CUDA engine build で `mmvq_il_parity` をビルドして実行する必要がある。CTest では `STRATA_ENABLE_CUDA` 条件内にテスト実行ファイルが登録されている。（`engine/cmake/strata_gpu_engine.cmake:813-818`）
- `MMVQ_IL_ONLY` が設定されていても、GPU parity 実行は選択されたケースに対してのみ行われる。ケースに一致しない場合、ケース本体は実行されないが、テーブル検査は実行される。（`engine/src/kernels/mmvq_il_parity.cpp:509-524`）
- CTest の `mmvq_il_parity_89table` は `STRATA_MMVQ_IL_89=1;MMVQ_IL_ONLY=no-such-case` を設定する。ソースコメントもこれをケース不一致によるテーブル検査専用と説明している。（`engine/cmake/strata_gpu_engine.cmake:819-821`）
- CLI 引数との優先順位や他の `MMVQ_IL_ONLY` 読み取り箇所はない。ベンチマーク引数が指定されてもケース選択条件は同じ。（`engine/src/kernels/mmvq_il_parity.cpp:471-490,521-524`）

## 実行時の詳細

変数は `main()` の一回の実行中、引数処理、CUDA stream 作成、必要ならベンチマーク前の warm-up、`check_tables()` の後に読み取られる。読み取り値はローカル変数 `only` に保持され、このプロセス実行中に再読込・更新されない。プロセス起動後の環境変更がこのループへ反映される経路はない。（`engine/src/kernels/mmvq_il_parity.cpp:471-490,491-523`）

選択された各 `Case` に `run_case()` を呼び、同関数が parity 検査を行う。`--bench` 時は該当ケースだけが計時対象になるが、ケース選択より前の warm-up はフィルターに関係なく実行される。どのケースにも一致しない値では `run_case()` が呼ばれず、`bad` が 0 のままなら最終行は `mmvq_il_parity: OK (every case, T 1-8, rows 1/2/4 and the table, bitwise)`、終了コードは 0 になる。したがって、この OK 文言だけでは全ケースを実行したことは示せない。テーブル検査または選択ケースで失敗が記録された場合は `mmvq_il_parity: FAIL` を出し、終了コード 1 を返す。フィルター値自体に対する警告やエラー出力はない。（`engine/src/kernels/mmvq_il_parity.cpp:509-526`）

## ログと測定値

フィルター固有のログはない。CTest の `mmvq_il_parity_89table` は未一致値を設定してケースをスキップしつつテーブル検査を通す用途として登録されている。（`engine/cmake/strata_gpu_engine.cmake:819-821`）

## 根拠

- `engine/src/kernels/mmvq_il_parity.cpp:103-143,471-526` — ケース一覧、起動処理、環境変数の読み取り、ケース選択、出力と終了コード。
- `engine/cmake/strata_gpu_engine.cmake:813-825` — CUDA 条件、実行ファイルと CTest の登録、`mmvq_il_parity_89table` の環境設定。
- `docs/MMVQ_IL_TABLE.md:26-28` — 当該実行ファイルのビルド・起動手順。環境変数の振る舞いはソースコードを根拠とした。
