# `--batch-mtp`（Qwen3.6 engine）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata --model Qwen3.6 の GGUF ...`（family 振り分け後）または `strata-q36` |
| オプション | `--batch-mtp` |
| 別名 | なし |
| 値 | 値を取らない boolean flag。既定値は無効 |

## 役割

Qwen3.6 engine の複数 serve slot の decode window で、greedy slot ごとに MTP block が提案した次 token を検証行として加えます。主モデルが提案を採用した slot は、その window で通常 token に続くもう1 token も進めます。オプション自体は提案を行う MTP draft 数を設定しません。`--mtp N` で draft 数を指定します（`src/qwen35/q36_engine.cu:3213-3216, 3741-3742, 3767-3777`）。

## 使い方

```sh
strata --model Qwen3.6-35B-A3B.gguf --serve --batch 2 --mtp 1 --batch-mtp
```

この例は Qwen3.6 family として認識される GGUF を使い、serve mode で2 slotを作り、MTP draft を1段有効にして batch MTP を要求します。実際のファイル名は手元の GGUF に合わせてください。`strata` は `--model` または `--native` の GGUF family を読み、Qwen3.6 (`qwen35moe`) なら専用 engine に引き渡します。専用実行ファイル `strata-q36` も同じ parser を使います（`src/program/generate.cpp:2393-2408`, `src/qwen35/q36_main.cpp:1-5`, `CMakeLists.txt:776-794`）。

## 値と既定値

- 引数 parser は `--batch-mtp` を見つけると boolean を true にするだけで、値を読みません。未指定時は false です（`src/qwen35/q36_engine.cu:3741-3742, 3776-3778`）。
- `--batch`（alias `--slots`）は別に session 数を受け取ります。engine の session 数は少なくとも1に制限され、複数 session では slot ごとの KV / recurrent state を確保します（`src/qwen35/q36_engine.cu:1194-1208, 1339-1343`）。
- `--mtp N` の既定値は0、許容範囲は0〜7 drafts です。`--mtp` が正でも、読み込んだモデルに MTP block がなければ実効 draft 数は0になります（`src/qwen35/q36_engine.cu:3737, 3767-3773, 3807-3812, 3882-3883`）。
- 同じ有効化条件を環境変数 `STRATA_BATCH_MTP` でも指定できます。専用 engine は変数が存在し、その値が文字列 `"0"` 以外なら有効扱いします（空文字も有効扱い）。CLI flag と環境変数の論理和で判定します（`src/qwen35/q36_engine.cu:3883-3887`）。

## 実行時の動作

設定が有効でも、batch MTP は serve loop の decode window でのみ使われます。active slot の数を `S` とすると、最大 `kVerify - S` の提案行が空いている場合に、その範囲で greedy slot を順番に候補とします。sampling が必要な slot は提案候補になりません。空き行または greedy slot がなければ通常の batch window に進みます（`src/qwen35/q36_engine.cu:3213-3234, 3351-3360`）。

候補 slot については MTP block から proposal を得て、通常の次 token と proposal を同じ window で主モデルに通します。主モデルの greedy token が proposal と一致し、EOS・停止・生成上限・context 上限に当たらない場合に proposal も採用し、その slot は2行を commit します。一致しなければ通常 token の1行だけを commit します（`src/qwen35/q36_engine.cu:3235-3263, 3273-3282, 3310-3347`）。

したがって `--batch-mtp` だけを `--tokens` の単発生成や benchmark に付けても batch window は走りません。実際の利用には serve mode、2以上の session、モデル内 MTP block、および `--mtp N` が必要です（`src/qwen35/q36_engine.cu:3882-3890, 3935-3957`）。

## 適用条件と副作用

- この専用経路は `STRATA_HAVE_QWEN35` が定義された `strata` build、または `strata-q36` executable が含まれる build で利用できます。CMake は `STRATA_HIP_GFX906` の場合に専用 engine library / executable を追加しません（`CMakeLists.txt:778-794`）。
- `--batch-mtp` が指定されても、実効 session 数が2未満、`--mtp` が0、またはモデルに MTP block がない場合は有効になりません。CLI flag を指定していたときは `strata-q36: --batch-mtp needs --batch N (2 or more) and --mtp N: ignored` を stderr に出します。これはこの条件に対する警告であり、flag の不足だけで parser が終了するわけではありません。環境変数だけで有効化を試みた場合、この警告条件は CLI flag の有無に依存します（`src/qwen35/q36_engine.cu:3882-3888`）。
- `--serve` ではない経路では `E.bmtp` が設定されても `Serve::window()` を通らないため、slot ごとの提案検証は発生しません（`src/qwen35/q36_engine.cu:3888-3890, 3916-3957`）。
- 提案には MTP block の追加計算が必要です。複数 slot の state / KV cache にも VRAM が必要で、不足時は engine が `not enough VRAM for ... slots` を stderr に出して終了コード1で終了します。このメモリ判定は session 確保のもので、batch MTP flag 固有の追加メモリ量はソースから数値化できません（`src/qwen35/q36_engine.cu:1456-1469, 3213-3253`）。
- batch MTP の採用数は slot 終了時に stderr へ `strata batch: slot ... MTP proposals accepted` として出ます。serve protocol の token / 完了通知は stdout に `BT` / `BDONE` 行で出力されます（`src/qwen35/q36_engine.cu:3280-3303`）。

## 出力とエラー

- option 自体に値は不要です。別の値を続けて書いた場合の専用 validation はなく、その文字列は後続 parser iteration で別引数として扱われます（`src/qwen35/q36_engine.cu:3742-3747, 3776-3778`）。
- `--mtp` の値が0〜7の範囲外なら stderr に `strata-q36: --mtp takes 0 .. 7 drafts` を出し、終了コード2です。モデル読み込み失敗はエラーメッセージを stderr に出し、終了コード1です（`src/qwen35/q36_engine.cu:3807-3815`）。
- 不明な引数は通常 parser では usage を stderr に出して終了コード2です。serve mode では未知の `--...` 引数を警告して読み飛ばす経路があります（`src/qwen35/q36_engine.cu:3782-3795`）。

## 根拠

- `src/qwen35/q36_engine.cu:3735-3778` — Qwen3.6 parser、既定値、`--batch-mtp` の値なし flag 定義。
- `src/qwen35/q36_engine.cu:3807-3815, 3882-3890` — `--mtp` 範囲検証、モデルの MTP 有無を反映する実効条件、serve への分岐と不足条件の警告。
- `src/qwen35/q36_engine.cu:3213-3360` — 候補 slot の選定、提案検証、採用時の行 commit、通常 window への fallback。
- `src/qwen35/q36_engine.cu:3280-3303` — proposal の採否、stdout protocol 出力、stderr の採用数。
- `src/qwen35/q36_engine.cu:1456-1469` — 複数 session の VRAM 見積もりと不足時の終了。
- `src/program/generate.cpp:2393-2408`, `src/qwen35/q36_main.cpp:1-5`, `CMakeLists.txt:776-794` — family dispatch と専用 `strata-q36` executable。
- 索引ではこの option は `strata-engine/qwen36` scope に掲載されています。通常 engine parser にも同名 option がありますが、意味・実装が異なるため本書は [`strata-engine/root/--batch-mtp.md`](../root/--batch-mtp.md) と統合しません（`docs/cli/README.md:1130-1144, 1318-1326`）。

調査は checkout 内の上記ソースを対象としました。Release artifact や同 revision の既存 `strata-q36 --help` は確認・実行していません。
