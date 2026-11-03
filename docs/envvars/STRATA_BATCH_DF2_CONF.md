# `STRATA_BATCH_DF2_CONF`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`--serve` のバッチスロットで DFlash2 の追加 draft row を何行使うかを、各 draft の selector 確率の累積積で制限します。閾値 `P` が正の場合、各スロットの確率を順に掛け、積が `P` 以上の間だけ draft row を残します。この変数は DFlash2 バッチ機能自体を有効化せず、機能が稼働しているときの row 数を制御します。

環境変数を読むのは `src/program/generate.cpp` のバッチ窓初期化時の1箇所です。値はその時点で `const double` に読み込まれ、slot ごとの窓構築で使われます。リクエストごと・窓ごとの再読み込みや static cache はありません（`src/program/generate.cpp:13599-13605,13891-13909`）。

## 値と判定

空でない環境値には `std::atof` を適用します。文字列全体の検査、エラー検出、範囲制限はありません。空文字または未設定では CLI の `--draft-conf` が正値ならそれを使い、そうでなければ `0.35` です。

| `STRATA_BATCH_DF2_CONF` | 採用値 | row 選別への影響 |
|---|---:|---|
| 未設定または空文字 | `--draft-conf` が `> 0` ならその値、そうでなければ `0.35` | 正の閾値として累積確率を判定 |
| 非空で `atof` の結果が正 | 変換結果をそのまま使用（`--draft-conf` より優先） | 累積積が閾値以上の draft row を残す |
| 非空で `atof` の結果が `0` 以下、または正値比較が成立しない | 変換結果をそのまま使用 | 閾値判定を行わず、他の row 上限まで使う |

`atof` が数値として読める先頭部分を変換するため、たとえば数値の後ろに文字が続いても先頭の数値が採用されます。数値に変換できない非空文字列は通常 `0` となり、閾値判定を無効にします。値を `0` にしても DFlash2 drafts 自体は止まりません。CLI の `--draft-conf` は `std::clamp(..., 0.0, 1.0)` で制限されますが、この環境変数には同じ clamp がありません（`src/program/generate.cpp:3590,13600-13603`）。

`--draft-conf` は環境値が未設定または空文字の場合だけ fallback として使います。非空の環境値があれば、その変換結果が CLI 値に優先します。

## 有効になる条件

この閾値が実際に使われるには `batch_df2` が有効である必要があります。コード上の主な条件は次のとおりです。

- `STRATA_HAVE_DFLASH2` が定義されたビルドであること。未定義の場合、`batch_df2` はコンパイル時定数 `false` です（`src/program/generate.cpp:6684-6692`）。
- Metal 以外で、明示的な `--draft dflash2`、`--batch >= 2`、`--serve`、`!split_same` が成立すること。`--draft auto` は対象外です。
- `STRATA_BATCH_DF2=0...` で明示的に無効化していないこと。`STRATA_BATCH_DF2` が非空で先頭文字が `0` 以外なら強制要求できます。未設定時は layer split があり、`batch_groups_for(false).groups <= 1` の場合だけ既定で要求されます。
- 要求後の `batch_mtp` 条件も通ること。たとえば `--spec >= 2` が必要で、layer split 上の helper expert cache とは併用されません。pipelined groups で batch drafts が動かない条件もあります。
- solo DFlash2 drafter が起動し、各 slot drafter の割り当て・bind・prepare が成功すること。

Metal は `batch_df2_wanted` を常に false にします。機能の要求条件に合わない場合は `strata generate: WARNING: ... is off: ...` が stderr に出ます。DFlash2 が起動しない場合も警告され、slot drafts は無効になります（`src/program/generate.cpp:6464-6480,6482-6506,6684-6692,6820-6840,11185-11196`）。

## 実行時の詳細

各 batch window の開始時に、稼働中 slot の数 `nact` と窓の余剰 row 数から、各 slot の基本 `want` を割り当てます。その後、DFlash2 が作れる上限、slot の残り生成数、context の残り、`STRATA_BATCH_DF2_MAXX` の上限（未設定・空なら `99`）で `want` を制限します。draft が準備済みで `df2_conf > 0` の場合、`q.dprob` の先頭から積を計算し、積が閾値以上である間だけ `want` を残します。閾値に達しない最初の row とそれ以降は追加しません（`src/program/generate.cpp:13887-13909`）。

したがって、高い閾値は各 slot の draft row を減らし、閾値より累積確率が低い場合はその slot の draft row が 0 になります。閾値が正でない場合はこの確率による削減を行いませんが、窓の余剰、DFlash2 の row 上限、残り token/context、`STRATA_BATCH_DF2_MAXX` による上限は引き続き適用されます。

この変数の値や閾値判定結果を直接表示するログはありません。DFlash2 slot drafter の起動時には slot 数や VRAM 使用量、ready 状態が stderr に出ます。clone/bind/prepare の失敗はエラーを出して終了します。 deferred row の catch-up 失敗は stderr に `catch-up failed ...: no drafts for it this round` と出し、その slot の当該 round の追加 draft を見送ります。窓後の gather/draft 処理の失敗は stdout に `ERR batch DFlash2 slot ...` を出して batch 処理を失敗させます（`src/program/generate.cpp:6823-6839,11185-11196,13914-13930,14084-14146`）。

## 根拠

- 環境値・fallback の読み取りと隣接する DF2 上限設定: `src/program/generate.cpp:13600-13605`。
- CLI `--draft-conf` の変換と範囲制限: `src/program/generate.cpp:3590`。
- `STRATA_BATCH_DF2` の要求条件、他の batch 条件および警告: `src/program/generate.cpp:6464-6506`。
- DFlash2 build guard、slot drafter の確保と起動失敗経路: `src/program/generate.cpp:6684-6692,6820-6840,11185-11196`。
- 閾値が slot ごとの draft row 数に作用する箇所: `src/program/generate.cpp:13887-13909`。
- 窓後の slot draft 実行と実行時エラー出力: `src/program/generate.cpp:14084-14146`。
