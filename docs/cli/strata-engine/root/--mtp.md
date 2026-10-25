# `--mtp`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジン） |
| オプション | `--mtp` |
| 別名 | なし |
| 値 | 通常経路では MTP runtime ディレクトリのパス。Qwen3.6 系へ委譲された場合は draft 数 `0`～`7`。 |

## 役割

通常のエンジン経路では、指定ディレクトリから MTP（multi-token prediction）ドラフターを読み込み、`--spec` の検証窓で次トークン候補を提案させます。最終的なトークンは verifier が確認します。ディレクトリは `tools/mtp_rt.py` が生成する runtime を想定しています（`src/program/generate.cpp:679-681`）。

ただし、Qwen3.6 系の GGUF（family `Qwen35Moe`）を指定して起動した場合は、通常 parser の前に `src/qwen35` 実装へ委譲され、同じ `--mtp` が数値の draft 数として解釈されます。この場合、別ディレクトリを指定する通常経路の意味とは異なります（`src/program/generate.cpp:2393-2407`、`src/qwen35/q36_engine.cu:3767-3773`）。

## 使い方

通常経路で、native model と対応する MTP runtime を使う例です。実行環境に合わせてパスを置き換えてください。

```sh
strata --native /models/model.gguf --mtp /models/mtp-runtime --spec 4 --tokens '1,2,3'
```

Qwen3.6 系の委譲経路では数値を指定します。

```sh
strata --native /models/qwen36.gguf --mtp 3 --tokens '1,2,3'
```

## 値と既定値

- 通常 parser の値は次の argv 要素をそのまま文字列として受け取り、パス形式や範囲の事前検証はしません。省略時の値は空文字列で、MTP を使いません（`src/program/generate.cpp:679-680,2418-2421,2623`）。
- `--mtp` の値を末尾で省略すると stderr に `--mtp needs a value` を出して終了コード 2 で終了します。通常 parser は同じ値を複数回受け取ると、後の値で上書きします（`src/program/generate.cpp:2418-2421,2623`）。
- 通常経路では `--spec` が 2 未満なら `--mtp` は stderr に無視する旨を出してクリアされます。MTP を有効にするには `--spec 2` 以上が必要です（`src/program/generate.cpp:5455-5459`）。
- Metal build では、受け取った runtime directory の重みを通常の CUDA/HIP loader で直接読むのではなく、既定で `<runtime-dir>/../mtp-q2_0.gguf` を MTP GGUF として開きます。`STRATA_METAL_MTP_GGUF` が設定されていれば、その値のパスを選びます（`src/core/mtp.cpp:251-258`、`metal/src/engine/window.cpp:2655-2675,1616-1621`）。環境変数の詳細は [`STRATA_METAL_MTP_GGUF`](../../../STRATA_METAL_MTP_GGUF.md) を参照してください。
- Qwen3.6 系では、値の先頭文字が数字なら `atoi` で数値化します。先頭が数字でない値（例: runtime ディレクトリ名）は無視され、stderr に注意が出ます。数値化後は 0～7 の範囲が必要で、範囲外は stderr にエラーを出して終了コード 2 になります（`src/qwen35/q36_engine.cu:3767-3773,3807`）。先頭が数字以外なら数値範囲検査には入りません。
- Qwen3.6 系の未指定値は 0（MTP speculative draft なし）です。GGUF 内の MTP block をロードするかは draft 数が 0 より大きい場合に選ばれます（`src/qwen35/q36_engine.cu:3735-3738,3811-3812`）。

## 実行時の動作

通常経路では `--mtp DIR` と `--spec >= 2` のとき、エンジンは `MtpDrafter::load()` にディレクトリ、窓サイズ、`--mtp-window` の値を渡します。`--mtp-window` の既定値は 32768、0 は全 cell を参照する設定です（`src/program/generate.cpp:680-681,5455-5473`）。load は `DIR/dense.txt` を index として読み、`DIR/dense.bin` と routed expert 重み `DIR/experts.bin` を扱います（`src/core/mtp.cpp:251-305,307-345`）。

MTP は推論のドラフトを担います。`--native` でロードした head が必要で、bind 時に native head がない場合は `mtp: the draft layer needs the native head (--native)` として失敗します（`src/core/mtp.cpp:671-678`）。`--serve` では MTP は任意で、省略時は suffix/prompt lookup draft または通常の一 token ずつの decode が使われ、各 verify window は引き続き実モデルで確認されます（`src/program/generate.cpp:8354-8366`）。

Qwen3.6 系は `--mtp N` を GGUF 自身に含まれる MTP block の speculative draft 数として使います。greedy で単独処理中の要求が対象で、sampling 要求や他要求と同時処理中はこの speculative 経路を使わず、候補は verifier で確認されます（`src/qwen35/q36_engine.cu:3585-3588,3642-3653`）。値が 0 より大きくても GGUF に MTP block がない場合、実際の draft 数は 0 になります（`src/qwen35/q36_engine.cu:3883`）。

## 適用条件と副作用

- 通常経路で `--spec < 2` の場合は値を無視します。`--spec >= 2` でも `--mtp` を省略した場合は MTP は動かず、`--serve` では前述の lookup または通常 decode 経路になります（`src/program/generate.cpp:5455-5459,8361-8366`）。
- runtime の `dense.txt` が開けない、行形式が壊れている、`dense.bin` が読めない、または CUDA VRAM 割当てに失敗する場合、load はエラー文字列を返します（`src/core/mtp.cpp:283-303`）。`experts.bin` の open・読込・サイズ不足などにも失敗経路があります（`src/core/mtp.cpp:307-345`）。
- Metal build の MTP GGUF は `Window::mtp_load()` が開き、Metal buffer として wrap できない場合はエラーになります（`metal/src/engine/window.cpp:1616-1621`）。
- ディレクトリのパスはセッションの model fingerprint にも含められ、`dense.bin`、`dense.txt`、`experts.bin`、`draft_vocab.bin` が入力ファイルとして追跡されます（`src/program/generate.cpp:9410-9424`）。
- Qwen3.6 系で非数値パスを指定した場合、指定値は注意表示のうえ無視されます。MTP block の存在自体はモデルロード時に確認されるため、draft 数が有効でも block がなければ MTP draft は無効です（`src/qwen35/q36_engine.cu:3767-3773,3883`）。

## 出力とエラー

- `--spec < 2` の通常経路は `strata generate: --mtp is ignored without --spec T (T >= 2)` を stderr に出し、処理を続けます（`src/program/generate.cpp:5455-5459`）。
- MTP load 失敗時は `strata generate: <原因>` と空き VRAM の補足を stderr に出し、通常経路は終了コード 1 で終了します（`src/program/generate.cpp:5470-5472`）。bind 失敗も原因を stderr に出し、終了コード 1 です（`src/program/generate.cpp:16143-16146`）。
- Qwen3.6 系で非数値値を渡した場合は `strata-q36: ignoring --mtp ...` を stderr に出して続行します。範囲外の draft 数は終了コード 2 です（`src/qwen35/q36_engine.cu:3767-3773,3807`）。

## 根拠

- parser、値要求、通常経路の既定値: `src/program/generate.cpp:679-681,2418-2421,2623`。
- MTP 適用条件、load、native head の要件: `src/program/generate.cpp:5455-5473,16143-16146`、`src/core/mtp.cpp:251-305,671-678`。
- `--serve` での省略時の経路: `src/program/generate.cpp:8354-8366`。
- runtime ファイルを入力として扱う箇所: `src/program/generate.cpp:9410-9424`。
- Metal build の別 runtime 選択: `src/core/mtp.cpp:251-258`、`metal/src/engine/window.cpp:1616-1621,2655-2675`。
- Qwen3.6 系への切替えと `--mtp` の別解釈: `src/program/generate.cpp:2393-2407`、`src/qwen35/q36_engine.cu:3735-3738,3767-3773,3807-3814,3883`。
- ソース内の `usage()` は `--mtp-window`、`--mtp-max-t`、関連する MTP オプションを列挙しますが、`--mtp` 自体の行は確認できませんでした（`src/program/generate.cpp:935-949`）。同一 revision の既存バイナリ help は利用せず、説明は parser と実装に基づきます。
