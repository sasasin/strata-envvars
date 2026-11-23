# `HY4_AB_SKIP_PLAIN`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

## 役割

Metal 版 `strata-hy4-metal` のオフライン A/B 比較で、通常（plain）生成の測定を飛ばす診断用スイッチ。A/B 分岐に入ったとき、この環境変数が未設定なら `plain_gen` で `--gen` トークンを生成し、設定されていればその呼び出しを省略する。DFly2 の speculative run 自体はその後も実行されるため、この変数は DFly2 の生成を無効化するものではない（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1819-1848,1898-1920`）。

## 値と判定

`getenv("HY4_AB_SKIP_PLAIN")` のポインタが null かどうかだけを判定する。文字列を parse せず、空文字を含む設定済みの値はすべて plain 生成を飛ばす。`0`、`false`、空白、大文字小文字の違いも値として検査されない。未設定の場合だけ plain 生成を試みる（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1903`）。

| 条件 | unset | 設定時に plain 生成を飛ばす値 | plain 生成を飛ばさない値 |
|---|---|---|---|
| Metal runner の A/B 分岐 | `plain_gen` を呼ぶ | 空文字、`0`、`1`、`false`、その他すべて（環境変数が存在する場合） | なし（環境変数が存在しない場合のみ） |

## 有効になる条件

- A/B 分岐 `spec_mode && ab_rounds > 0` に到達する必要がある。`--ab` は `atoi` で読み取られ、値が正の場合に A/B ループへ進む（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1572,1898-1899`）。
- この分岐の前に `--par-m` と `--bench-m` の処理はそれぞれ終了する。実際に A/B 分岐へ到達する `spec_mode` では `--gen > 0`、`--draft off` ではないこと、モデルに DFly2 の所定 tensor があること、runner の chunk `r.Tc >= 16`、`--all-logits` でないこと、画像レコードがないことが必要（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1755-1762,1857-1898`）。
- `--serve` はオフライン処理より前にサーバー処理へ移るため、この A/B 分岐では読まれない（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1636-1674`）。他 backend の実装や共通 helper 経由の参照はなく、この名前の唯一の参照は Metal runner 内である。
- `--ab` が 0 以下、speculative mode が成立しない、またはサーバー経路の場合、この変数の分岐は実行されず影響しない。CLI オプションによる値の上書き・優先順位はない。

## 実行時の詳細

A/B ループの各ラウンドで `getenv` を直接呼び、plain 側の測定開始後に結果を判定する。関数内 static cache や起動時の保存はない。未設定なら `plain_gen` を実行し、失敗時には `forward: %s` を stderr に出して終了コード 1 で終了する。plain 側の前後には `restore()` が呼ばれるため、環境変数が設定されて plain 側を飛ばす場合も、後続の speculative run 前の復元処理は残る（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1832-1847,1849-1856,1898-1914`）。

設定済みの場合、plain 側の token vector `pids` は空のままですが、speculative run、`[ab]` の stdout 出力、`sp.report`、1 ラウンド目の `gen_ids_plain.txt` / `gen_ids_spec.txt` 出力処理は続く。したがって plain token 数と一致 prefix は 0 になり、速度比の計算では plain throughput が 0 になるため、通常の A/B 速度比較値として解釈できない（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1901-1927`）。この名前を理由とする専用ログや警告はない。

## ログと測定値

環境変数専用のログ・警告はない。A/B 行は引き続き stdout に `[ab] ... plain ... dfly2 ... speedup ... identical prefix ...` の形式で出力される。設定時は plain 側の token 数が 0 のままである。Strata の資料にこの変数の測定値は確認できない（出力処理: `engine/src/hy4flash/metal/hy4_metal_main.cpp:1918-1927`）。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1819-1848` — `plain_gen` が prefill 済み状態から `gen` 回まで通常 decode し、forward failure 時に `false` を返す。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1488-1513,1556-1574,1636-1674` — CLI 初期値と `--gen` / `--ab` の parse、およびサーバー経路。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1755-1762,1857-1898` — speculative mode の条件、先行する parity / bench 経路の終了、A/B 分岐への到達条件。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1898-1927` — ラウンドごとの環境変数判定、plain skip 後も継続する speculative run と A/B 出力。
