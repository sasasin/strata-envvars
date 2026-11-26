# `STRATA_Q36_PLACE_DEBUG`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Qwen 3.5/3.6 エンジンの自動 prefill chunk 選択結果を、stderr に 1 行表示する診断スイッチ。chunk サイズや expert placement の計算そのものは変えない。`engine/src/qwen35/q36_engine.cu` の `strata::qwen35::run` が値を直接読み、選択済み chunk と VRAM 計算値を出力する（`engine/src/qwen35/q36_engine.cu:5339-5343,5475-5523`）。

## 値と判定

`std::getenv` の戻り値が null かどうかだけを判定し、値の内容は parse しない。従って空文字を含む、設定されているすべての値が真となる。大文字小文字、空白、数値としての妥当性、境界値は調べない。未設定なら診断行を出さない（`engine/src/qwen35/q36_engine.cu:5518-5520`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| 自動 chunk 選択 (`chunk == 0`) | 出力なし | `1`、`0`、`true`、`false`、`0anything`、空文字 | 設定値として無効な値はない。環境変数が未設定の場合のみ出力なし |
| CLI で明示した chunk (`chunk != 0`) | 判定箇所に到達しない | 該当なし | 設定値にかかわらず出力なし |

既定の `chunk` は 0（自動）。`--chunk auto` / `--prefill auto` も 0 にし、数値指定はその値を設定する。自動選択の分岐に入った場合のみ `STRATA_Q36_CHUNK` があれば `atoi` した値を 256..4096 に clamp して選択値を上書きし、その後この診断スイッチを確認する。この環境変数自体には既定値・数値変換・範囲制限はない（`engine/src/qwen35/q36_engine.cu:5342,5363,5475-5477,5517-5520`）。

## 有効になる条件

- `strata::qwen35::run` で `chunk == 0` の自動選択経路を通る必要がある。CLI の既定値は自動だが、明示的な `--chunk N` / `--prefill N` はこの経路を迂回する（`engine/src/qwen35/q36_engine.cu:5342,5363,5475-5476`）。
- 自動選択と診断はモデル読み込み後に実行される。モデル読み込みが失敗すると、ここへ到達せず診断行も出ない（`engine/src/qwen35/q36_engine.cu:5458-5465,5475-5523`）。
- `STRATA_Q36_CHUNK` が設定されていても診断行は抑止されず、同変数による上書き後の chunk 値を表示する。明示 CLI chunk の場合は `STRATA_Q36_CHUNK` と本変数の両方がこの分岐で参照されない（`engine/src/qwen35/q36_engine.cu:5517-5520`）。
- 読み取り箇所は CUDA/HIP エンジンの `.cu` 実装内にある。CPU-only の別経路について、この読み取りによる挙動は確認できない。

## 実行時の詳細

`run` のローカル変数 `chunk` は初期値 0。モデル読み込み後、自動選択では CUDA の空きメモリを取得し、モデルの expert サイズや設定に基づいて chunk を選ぶ。選択後に `STRATA_Q36_CHUNK` の上書きを適用し、環境変数が設定されていれば stderr に `free`、`raw`、`packed`、main experts の容量と最終 chunk を表示する。その後 `E.init` と `place_experts` に進む。したがって本変数はログ条件だけを変え、選択処理・expert 配置・生成内容に対する制御や優先順位を持たない（`engine/src/qwen35/q36_engine.cu:5475-5525`）。

値は自動選択分岐に到達した時点で都度 `getenv` され、static cache はない。読み取りはこの分岐中の 1 回であり、分岐を抜けた後の環境変更を同じ実行で再評価しない（`engine/src/qwen35/q36_engine.cu:5518-5520`）。

## ログと測定値

有効時に stderr へ次の形式で 1 行出る。各容量は GiB 表示で小数点以下 2 桁、chunk は整数。

```text
strata-q36: chunk rule: free %.2f GiB (raw %.2f, with %.2f packed), main experts %.2f GiB, chunk %d
```

未設定時はこの行を出さない。明示 CLI chunk、またはモデル読み込み失敗時もこの行は出ない。この変数に関する測定値はソースで確認できない（`engine/src/qwen35/q36_engine.cu:5458-5465,5518-5520`）。

## 根拠

- `engine/src/qwen35/q36_engine.cu:5339-5343,5363` — run の既定値と CLI chunk 指定。
- `engine/src/qwen35/q36_engine.cu:5458-5465,5475-5523` — モデル読み込み、自動選択、環境値による上書き、ログ、後続の初期化・配置。
- `engine/src/qwen35/q36_engine.cu:5517-5520` — `STRATA_Q36_CHUNK` の上書き、対象変数の設定有無判定と stderr 文言。
