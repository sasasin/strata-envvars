# `strata-hy4-metal --save-logits`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4`（Metal スコープ） |
| コマンド | `strata-hy4-metal` |
| オプション | `--save-logits` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

オフライン推論で prompt の prefill を終えたとき、最終チャンクの logits を NumPy の float32 ファイル `logits.npy` に保存します。通常は最終チャンクの末尾トークン 1 行を保存し、`--all-logits` を併用すると最終チャンク全行を保存します。生成後の各トークンの logits を追記するフラグではありません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1799-1808,1944-1976`）。

## 使い方

```sh
# --out のディレクトリが存在し、logits.npy がまだない場合の例
strata-hy4-metal --model SQ64.strata --tokens prompt.ids --save-logits --out ./logits-run
```

`--model` と `--tokens` を指定した通常のオフライン経路で使用します。`--out` を省略した場合の出力先はカレントディレクトリです（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1488-1490,1507-1517,1611-1614`）。

## 値と既定値

値・短縮別名はありません。parser は `--save-logits` を見つけると `save_logits = true` にし、初期値は `false` です。したがって省略時はこのフラグ単独では保存せず、同じフラグを繰り返しても真偽値を再設定するだけです。数値などの値を後ろに付ける構文はありません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1492,1504-1505,1554`）。

## 実行時の動作

prompt の最終チャンクを forward し、`r.head` と `r.run_all` で logits を計算した後、float 配列 `hl` を作ります。`--save-logits` または `--dump` のいずれかが指定されていれば、`<out_dir>/logits.npy` に形状 `(n, V)`、little-endian float32 (`<f4`) として保存します。`V` はモデルの vocabulary 数です（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1754,1799-1808`）。

`--all-logits` がない場合、最終チャンクの末尾位置だけを head に渡すため `n=1` です。併用時は最終チャンクの全 `T` 位置を渡すため `n=T` です。ここで保存対象は prefill の最終チャンクであり、前のチャンクや、後続の生成ステップの logits はこの保存処理の対象になりません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1802-1808,1829-1844,1951-1966`）。

`--dump` も logits 保存を有効にし、加えて `Runner` の dump を有効化して他の dump 出力にも影響します。`--save-logits` だけではその `Runner` dump フラグは有効になりません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1516,1721-1722,1808`）。

## 適用条件と副作用

- オフライン推論経路が対象です。`--load-only` はモデル読込後に早期終了し、`--serve` はサーバー処理へ分岐して戻るため、いずれもこのファイル保存箇所には到達しません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1635-1636,1674-1676,1802-1808`）。
- 保存先は `--out` の値に `/logits.npy` を連結したパスです。`--out` の既定値は `.` で、parser にディレクトリ作成や当該値の検証はありません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1489-1490,1510,1808`）。
- helper は `fopen(..., "wb")` を使うため、同名ファイルがあれば切り詰めて上書きします。出力ディレクトリは自動作成されません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:41-50`）。
- `--model` の読込、空 token 入力、画像処理、初期化、forward などが失敗して該当箇所より前に終了すれば保存されません（例: `engine/src/hy4flash/metal/hy4_metal_main.cpp:1620-1626,1701-1705,1762-1765,1776-1780,1794-1796`）。

## 出力とエラー

成功時の保存専用メッセージはありません。`fopen` が失敗した場合、helper は何も出力せずに戻り、呼び出し元も戻り値を確認しません。また `fwrite` / `fclose` の失敗も検査されないため、ソースからは保存成功を判定できません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:41-60,1808`）。

なお、parser は `--save-logits` を受理しますが、引数不足時に表示する usage 行にはこのフラグが記載されていません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1554,1611-1614`）。未知の引数は stdout に `ERR unknown flag ...`、stderr に `unknown arg ...` を出して終了コード `2` になります（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1604-1608`）。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1488-1517,1554` — Metal CLI の状態初期値、`--out` / `--all-logits` / `--save-logits` の parser 登録。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:41-60` — NumPy v1 float32 書き出し形式、上書きモード、およびファイル書込み失敗の扱い。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1635-1676` — `--load-only` と `--serve` の早期分岐。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1754,1799-1817` — logits の生成・切り出し・保存条件と出力形状。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1829-1844,1944-1976` — 生成経路では本オプションによる logits 保存を行わないこと。
