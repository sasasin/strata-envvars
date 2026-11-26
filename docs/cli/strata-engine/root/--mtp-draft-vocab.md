# `strata --mtp-draft-vocab`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数。サブコマンドなし） |
| オプション | `--mtp-draft-vocab` |
| 別名 | なし |
| 値 | `FILE`。draft head の token subset を格納したファイルへのパス |

## 役割

MTP または DFlash2 drafter が draft head に使う token subset ファイルを、通常の `<mtp>/draft_vocab.bin` の代わりに指定します。指定値は parser ではパス文字列として保存され、MTP bind 時または DFlash2 の head bind 時に読み込まれます。`generate.cpp` の parser には値の内容や存在確認がなく、使用する drafter と backend によって実際の読み込み経路が異なります。

## 使い方

```sh
# MTP ディレクトリ内の既定 draft_vocab.bin の代わりに別ファイルを使う
strata --pack MODEL --mtp MTP_DIR --mtp-draft-vocab ./data/draft_vocab_en.bin --spec 4

# DFlash2 単独起動で MTP ディレクトリなしに subset を指定する
strata --pack MODEL --draft dflash2 --draft-fallback none --draft-model PACK \
  --mtp-draft-vocab ./data/draft_vocab_en.bin --spec 4
```

## 値と既定値

- `FILE` は次の argv 要素をそのまま受け取ります。省略されていて値がない場合は `--mtp-draft-vocab needs a value` を stderr に出して終了コード 2 で終了します。後続の option 文字列も値として扱うため、値の欠落を option 名で判別しません。`--mtp-draft-vocab` を複数回指定した場合は、parser のループで後の値が前の値を置き換えます。 (`engine/src/program/generate.cpp:3842-3847`, `4142`)
- 値はファイルパス文字列です。parser 段階で空文字、存在、読み取り可能性、ファイル内容は検査しません。
- 明示指定がない場合、MTP 側の既定は `<mtp>/draft_vocab.bin` です。明示パスはこの既定より優先されます。 (`engine/include/strata/core/mtp.hpp:77-79,324-325`)
- MTP の CUDA/HIP bind はファイルを読み込め、サイズが 4 byte 以上かつ 4 の倍数なら int32 token ID の配列として扱います。ファイルがない、読み込めない、空、またはサイズが 4 の倍数でない場合、この subset は構築されず、全 head を使う経路になります。確認した bind 箇所では token ID の値域検証は行っていません。 (`engine/src/core/mtp.cpp:939-955`)

## 実行時の動作

- 通常の MTP 経路では、`--mtp` と `--spec >= 2` が有効なときに `MtpDrafter` へ明示パスを設定し、モデルの head から subset 行を gather します。subset の ID 配列と head 行を GPU メモリに確保し、stderr に subset の token 数と head サイズを出します。複数 GPU の layer split で drafter と head が別カードにある場合は、head 側で行を gather して drafter 側へ一度コピーします。 (`engine/src/program/generate.cpp:8243-8265`, `engine/src/core/mtp.cpp:939-988`)
- MTP が有効でない場合、この値だけでは MTP は起動しません。`--spec` が 2 未満ならエンジンは `--mtp` を無視してクリアします。 (`engine/src/program/generate.cpp:8243-8247`)
- Metal の通常 MTP window は `STRATA_METAL_DRAFT_VOCAB`、GGUF の隣にある `rt/draft_vocab.bin`、または build 同梱の `data/draft_vocab.bin` から選びます。`Window` のこの読み込み経路は `--mtp-draft-vocab` parser 値を使いません。従って通常 MTP の Metal 実行に対するこの CLI 値の効果は、確認した実装ではありません。 (`engine/metal/src/engine/window.cpp:2569-2582`; `engine/src/core/mtp.cpp:908-913`)
- `--draft dflash2` と `--draft-fallback none` の組み合わせでは、明示ファイルは DFlash2 の head subset として使われます。MTP layer をロードせず、`--mtp-draft-vocab FILE` だけで vocabulary file の指定を満たせます（ほかに `--draft-model PACK` と `--spec >= 2` が必要）。DFlash2 の語彙パスは明示値を優先し、未指定なら `<mtp>/draft_vocab.bin` を選びます。 (`engine/src/program/generate.cpp:6494-6509`)
- DFlash2 単独起動で明示ファイルが指定されていれば、そのファイルが存在するかを起動前に検査します。見つからない場合、whole-head 明示許可がなければ stderr に不足ファイルを示して終了コード 2 になります。Metal build は明示ファイル未指定の場合に限り、MTP directory の候補がなければ同梱 subset を使います。 (`engine/src/program/generate.cpp:6510-6527`; `engine/include/strata/spec/draft_vocab.hpp:23-32`)
- Serve のモデル fingerprint 対象に、MTP が有効で明示パスがある場合はそのファイルを `mtp draft_vocab` として加えます。MTP path が空なら MTP 関連ファイルを fingerprint に加えません。 (`engine/src/program/generate.cpp:13987-13995`; `engine/src/core/conversation_file.cpp:944-970`)

## 適用条件と副作用

- MTP の subset は draft 提案に使われ、target verifier が token を確定します。ファイルを読むほか、subset の head 行を GPU に確保するため、token 数に応じた VRAM を使います。確保失敗時は `mtp: the draft head does not fit` となり、MTP bind が失敗します。 (`engine/include/strata/core/mtp.hpp:72-79`; `engine/src/core/mtp.cpp:947-951`)
- `--mtp-q4 head` または `all` と併用すると、この subset head が Q4_0 化の対象です。subset が構築されなければ Q4 head 化は適用されず、全 head で draft する旨の stderr 警告が出ます。 (`engine/src/program/generate.cpp:4135-4142,8250-8253`; `engine/src/core/mtp.cpp:1007-1013`)
- `--draft dflash2` の solo 経路では、`--mtp-draft-vocab` の指定は subset ファイルの選択に使われ、MTP layer を使わない場合でも有効です。DFlash2 はサイズが 4 byte 以上かつ 4 の倍数のファイルを int32 単位で読み込みます。読み込んだ subset が空なら `bind_raw` は head 全体の行数を使うため、サイズ不整合や読み込み失敗は subset としては適用されません。 (`engine/src/core/dflash2.cpp:387-402,347-365`)
- Metal の DFlash2 solo 経路では `generate.cpp` の resolver がこの CLI 値を渡します。Metal 通常 MTP window の vocab 選択とは別経路です。 (`engine/src/program/generate.cpp:6514-6527`; `engine/metal/src/engine/window.cpp:2570-2582`)

## 出力とエラー

- 値の欠落: `--mtp-draft-vocab needs a value`（stderr、終了コード 2）。 (`engine/src/program/generate.cpp:3844-3846`)
- MTP bind の head 領域確保失敗: `mtp: the draft head does not fit` を呼び出し側が stderr に出し、generate/serve の起動処理は終了コード 1 を返します。 (`engine/src/core/mtp.cpp:947-951`; `engine/src/program/generate.cpp:13496-13501,24507-24510`)
- DFlash2 solo の必須条件不足は説明行を stderr に出して終了コード 2、subset ファイルが解決できない場合も不足パスを含むエラー行を stderr に出して終了コード 2 です。 (`engine/src/program/generate.cpp:6505-6509,6518-6524`; `engine/include/strata/spec/draft_vocab.hpp:30-32`)

## 根拠

- `engine/src/program/generate.cpp:1182-1183,1358-1361,4142` — option の定義、help 文言、parser 登録。
- `engine/src/program/generate.cpp:3842-3847,4268-4274` — 値取得規則、未知引数の失敗経路。
- `engine/include/strata/core/mtp.hpp:77-79,324-325` — 明示 path の保存と既定ファイルの解決。
- `engine/src/program/generate.cpp:8243-8265`; `engine/src/core/mtp.cpp:939-1014` — MTP への引き渡し、subset 読み込み・head 行確保・警告。
- `engine/src/program/generate.cpp:6494-6530`; `engine/include/strata/spec/draft_vocab.hpp:23-32`; `engine/src/core/dflash2.cpp:387-402` — DFlash2 solo の条件、ファイル解決と読込。
- `engine/metal/src/engine/window.cpp:2569-2582` — Metal 通常 MTP window の別の subset 解決。
- `engine/src/program/generate.cpp:13987-13995`; `engine/src/core/conversation_file.cpp:944-970` — serve fingerprint に含めるファイル。

調査範囲は指定 checkout の現行ソースです。ファイル内の int32 token ID 全ての値域妥当性や、外部で生成される subset の正しさは、MTP bind の確認範囲では検証処理を確認できませんでした。
