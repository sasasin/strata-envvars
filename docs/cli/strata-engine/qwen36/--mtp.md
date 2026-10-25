# `--mtp`（Qwen3.6 engine）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata --model <Qwen3.6 GGUF> ...`（family 振り分け後）、または `strata-q36` |
| オプション | `--mtp` |
| 別名 | なし |
| 値 | draft 数 `N`（0〜7）。parser の既定値は `0` |

## 役割

Qwen3.6 GGUF 内の MTP block を使い、greedy 生成で次 token 候補を先に提案して主モデルで検証します。`--mtp N` は提案する draft 数を指定します。MTP が提案した token は検証経路で採否を決めるため、この機能だけで通常の greedy 出力を draft の候補範囲に制限するものではありません（`src/qwen35/q36_engine.cu:2107-2109, 3735-3741, 3935-3957`）。

この文書の `--mtp` は Qwen3.6 用です。通常 engine の `--mtp` は draft layer のディレクトリを値に取る別実装であり、索引は parser の違いを `qwen36/` scope で区別しています（`docs/cli/README.md:1318-1323, 1341-1344`; 通常 engine parser: `src/program/generate.cpp:670-681, 2623-2624`）。

## 使い方

```sh
strata --model /models/qwen36.gguf --tokens 1,2,3 --mtp 4 --n 64
```

この例は Qwen3.6 family の GGUF を読み、token ID `1,2,3` を prompt として greedy 生成し、最大64 tokenを出力します。手元のモデルのパスと prompt token ID に置き換えてください。`strata` は `--model` または `--native` が指す GGUF の family が `Qwen35Moe` のとき Qwen3.6 parser に切り替えます。別 executable の `strata-q36` も同じ parser 関数を呼びます（`src/program/generate.cpp:2393-2408`, `src/qwen35/q36_main.cpp:1-5`）。

## 値と既定値

- `--mtp` は値必須です。値を省略すると `strata-q36: --mtp needs a value` を stderr に出し、終了コード2で終了します（`src/qwen35/q36_engine.cu:3742-3747, 3767-3773`）。
- 未指定時は `mtp_d = 0` で、MTP draft による生成は行いません。明示値の範囲は0〜7です。範囲外は `strata-q36: --mtp takes 0 .. 7 drafts` を stderr に出し、終了コード2です（`src/qwen35/q36_engine.cu:3737, 3807`）。
- parser は値の先頭文字が数字の場合に `atoi` で整数化します。そのため `4x` は4として扱われ、`-1` や `auto` のように数字で始まらない値は値を無視して警告を出します。後者はただちに parser error にはなりません。値は整数として指定してください（`src/qwen35/q36_engine.cu:3767-3773`）。
- 複数回指定した場合、数字で始まる指定はその都度 `mtp_d` を更新します。数字で始まらない指定は警告のみで既存値を更新しません（`src/qwen35/q36_engine.cu:3767-3773`）。

## 実行時の動作

値が1〜7でも、ロードした GGUF に MTP block がある場合に限り `E.mtp_d` に設定されます。モデル metadata の MTP layer 数が0なら `E.mtp_d` は0になり、MTP なしの通常経路を使います。ロード処理は MTP block がファイルに存在すれば `--mtp` の指定有無にかかわらず読み込みます。ソースコメントでは block による VRAM 使用量が `--mtp` の有無で変わらない設計としています（`src/qwen35/q36_engine.cu:1027-1031, 1090-1096, 3882-3885`）。

- 通常の `--tokens` 生成では、`E.mtp_d > 0` かつ `--force` が空、`--dump-full-logits` を開いていない場合に MTP speculative step を通ります。主モデルが draft を検証し、採用数に応じて次の token へ進みます（`src/qwen35/q36_engine.cu:3916-3920, 3935-3958`）。
- `--serve` では MTP draft 数が正で、sampling が必要でない request に speculative step を使います。sampling request や他 slot と同時進行中の通常 per-request speculative step はこの条件から外れます（`src/qwen35/q36_engine.cu:3585-3588, 3640-3665`）。複数 slot の decode window で proposal も検証する機能は `--batch-mtp` で別途有効にします。同 option は `--batch` が2以上で MTP draft 数も正であることを要求し、不足時は無視の警告を出します（`src/qwen35/q36_engine.cu:3883-3889`; [`--batch-mtp`](--batch-mtp.md)）。
- `--bench-pp` / `--bench-tg` の benchmark 分岐は MTP speculative loop より前に実行され、token-by-token の greedy decode を計測します。したがって `--mtp` を同時に指定しても、この benchmark loop は MTP draft を利用しません（`src/qwen35/q36_engine.cu:3890-3915, 3935-3944`）。

## 適用条件と副作用

- `strata` での family dispatch は `STRATA_HAVE_QWEN35` が定義された build に限られます。CMake は `STRATA_HIP_GFX906` の場合に `strata_qwen35` と `strata-q36` を追加しません。`strata-q36` は Qwen3.6 engine の単独 executable です（`src/program/generate.cpp:2393-2408`, `CMakeLists.txt:776-795`, `src/qwen35/q36_main.cpp:1-5`）。
- モデルに MTP block がないとき、正の値を指定しても実効 draft 数は0になります。明示した `--mtp` がその理由で無効になったという専用警告は確認できません（`src/qwen35/q36_engine.cu:3882-3885`）。
- 複数 session (`--batch`) では session ごとの KV cache / recurrent state に VRAM が必要です。割当見積もりを満たせない場合は `not enough VRAM for ... slots` を stderr に出して終了コード1で終了します。このチェックは batch session の確保に関するもので、`--mtp` 固有の追加 VRAM 量を数値で示すものではありません（`src/qwen35/q36_engine.cu:1452-1469`）。

## 出力とエラー

- 通常の MTP token 生成は stdout に `gen: <token IDs...>`、stderr に prompt / generation の時間と `MTP N drafts: accepted of offered` の統計を出します（`src/qwen35/q36_engine.cu:3951-3958`）。
- `--mtp` の値欠落または0〜7外の値は終了コード2です。値が数字で始まらない場合は `strata-q36: ignoring --mtp ...` を stderr に出して継続し、その後に必要な `--tokens` / `--serve` / benchmark 条件がなければ usage 相当のエラー（終了コード2）になる場合があります（`src/qwen35/q36_engine.cu:3767-3773, 3790-3795, 3807, 3916-3918`）。
- モデル読み込みが失敗した場合はエラーを stderr に出し、終了コード1です（`src/qwen35/q36_engine.cu:3811-3815`）。

## 根拠

- `src/qwen35/q36_engine.cu:3735-3778` — parser、値変換、既定値、オプション値がない場合のエラー。
- `src/qwen35/q36_engine.cu:3807-3815` — draft 数の範囲検証とモデル読み込み失敗。
- `src/qwen35/q36_engine.cu:1027-1031, 1090-1096, 3882-3885` — MTP block の読み込みとモデルに基づく実効値。
- `src/qwen35/q36_engine.cu:3585-3588, 3640-3665, 3935-3958` — serve / 単発生成で MTP を使う条件、採否統計。
- `src/qwen35/q36_engine.cu:3890-3915` — benchmark 分岐の動作。
- `src/qwen35/q36_engine.cu:1452-1469` — 複数 session の VRAM 判定と不足時の終了。
- `src/program/generate.cpp:2393-2408`, `src/qwen35/q36_main.cpp:1-5`, `CMakeLists.txt:776-795` — `strata` の family dispatch、単独 executable、build 条件。
- `docs/cli/README.md:1318-1323, 1341-1344` — `strata-engine/qwen36` scope と索引上の対象パス。

同 revision の既存 CLI `--help` と Release artifact は確認していません。本書は checkout 内ソースで確認できた parser と実行経路を記録しています。
