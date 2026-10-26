# `--tokens-file`

調査対象: Strata commit `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-q36ref` |
| コマンド | `strata-q36ref`（トップレベル） |
| オプション | `--tokens-file PATH` |
| 別名 | なし |
| 値 | 読み込む token ID 列のファイルパス |

## 役割

ファイルの内容を prompt token ID 列として読み込みます。`strata-q36ref` は Qwen3.6 reference path の照合用 executable で、通常の Terminal CLI や推論 engine の `strata` とは別の CLI です。CMake では GPU backend build 内に target が定義されています（`CMakeLists.txt:771-775`）。

## 使い方

```sh
strata-q36ref --model model.gguf --tokens-file ./prompt.ids
```

`--model` と、`--tokens` または `--tokens-file` から得られる空でない prompt が必要です。実行には GPU backend を有効にしてビルドした executable と対応するモデル・GPU 環境が必要です（`src/qwen35/q36ref.cu:771-788`）。

## 値と既定値

- 値は必須です。次の argv 要素をパスとして使います。値がない場合は `q36ref: --tokens-file needs a value` を stderr に出して終了コード `2` で終了します（`src/qwen35/q36ref.cu:727-732,736-737`）。
- この option 固有の既定値はありません。ファイルを指定すると `fopen(PATH, "rb")` で開き、最大 4096 byte ずつ読み取って内容を token 文字列へ追加します（`src/qwen35/q36ref.cu:736-742`）。
- ファイル内容は `--tokens` と同じ `parse_ids` に渡されます。カンマ、空白、改行、復帰文字を区切りとして走査し、各要素を `std::atoi` で整数化します。厳密な数値形式や token ID の語彙範囲を検査する処理はありません（`src/qwen35/q36ref.cu:708-717`）。
- ファイルが空、または `parse_ids` の結果が空なら、後段の必須 prompt 判定で拒否されます（`src/qwen35/q36ref.cu:766,771-774`）。
- 同じ `--tokens-file` を複数回指定すると、各ファイルの内容が区切りを自動挿入せず順に追加されます。境界で数値がつながらないよう、ファイル末尾などに区切りを含めてください（`src/qwen35/q36ref.cu:736-742`）。

## 実行時の動作

読み込んだ文字列は `parse_ids` で prompt の整数列に変換され、各 prompt 位置の forward 入力に使われます（`src/qwen35/q36ref.cu:766,802-805`）。`--tokens` と `--tokens-file` は排他的な指定として検査されていません。引数走査順に `--tokens VALUE` は token 文字列を置き換え、`--tokens-file PATH` は現在の文字列へファイル内容を追加します。そのため、`--tokens-file a --tokens 1,2` では先に読んだファイル内容が置き換わり、`--tokens 1,2 --tokens-file a` では `1,2` の後へファイル内容が追加されます（`src/qwen35/q36ref.cu:734-742`）。

prompt の長さは `--n`（既定 `64`）などから決まる処理位置数と合わせて `--ctx`（既定 `4096`）と比較されます。合計位置数が context を超えると、ファイル読み込み・モデル読み込み・GPU state 初期化の後でエラー終了します（`src/qwen35/q36ref.cu:724,775-800`）。

## 適用条件と副作用

- `fopen` に失敗すると `q36ref: cannot read the tokens file` を stderr に出し、終了コード `2` で終了します。診断には失敗したパスが含まれません（`src/qwen35/q36ref.cu:736-739`）。
- 読み取りは `fread` が 0 を返すまで続き、その後 `fclose` されます。読み取り回数・close の戻り値を検査する処理や、I/O error と EOF を区別する処理は確認できません（`src/qwen35/q36ref.cu:739-742`）。
- token ID の形式・範囲検証はありません。変換は `atoi` によるため、不正な値や語彙外 ID の結果はこの CLI の parser だけでは拒否されません。語彙外 ID を実際に GPU 上で処理した場合の結果は調査していません。
- この option 自体は出力ファイルを作成しません。prompt に続く生成や dump 出力は他の option と実行経路に従います。

## 出力とエラー

- 値欠落: stderr に `q36ref: --tokens-file needs a value`、終了コード `2`。
- ファイルを開けない: stderr に `q36ref: cannot read the tokens file`、終了コード `2`。
- prompt が空: stderr に `q36ref: --model and --tokens are required`、終了コード `2`。
- 未知の引数（`--help` を含む）: usage を stderr に出し、終了コード `2`。専用の help option はありません（`src/qwen35/q36ref.cu:759-764`）。
- 正常終了時、greedy token ID 列は stdout の `gen:` 行に出て、処理時間等は stderr に出ます（`src/qwen35/q36ref.cu:826-830`）。

## 根拠と調査範囲

- `src/qwen35/q36ref.cu:722-764` — 引数 parser、値取得、ファイル open/read/close、未知 option 時の usage。
- `src/qwen35/q36ref.cu:708-717,766,771-774` — token 文字列の分割・整数変換と空 prompt の検査。
- `src/qwen35/q36ref.cu:775-805,826-831` — モデル・state 初期化後の context 判定、prompt の forward、出力と終了。
- `CMakeLists.txt:771-775` — `strata-q36ref` target とリンク先。
- `docs/cli/README.md:1487-1503` — `strata-q36ref` を照合用の独立 CLI として扱い、本 option を root scope に索引化。

記述は上記 revision の checkout 内の parser・使用箇所と CMake 定義に基づきます。同一 revision の実行バイナリや Release 配布物は確認しておらず、`--help` も実行していません。GPU 上の token ID 不正値の挙動は実行確認していません。
