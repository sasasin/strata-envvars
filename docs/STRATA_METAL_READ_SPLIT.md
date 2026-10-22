# `STRATA_METAL_READ_SPLIT`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

Apple Metal エンジンの expert streaming が、一つの expert を SSD から読む際に何個の I/O piece に分けるかを指定します。分割した piece は I/O worker のキューに個別の job として入り、単一 expert の読み込み中に複数 worker が並行して処理できる形になります。読み取り元が `.experts` 連続コピーか GGUF 本体かで、分割単位が異なります。

## 値と判定

`env_int()` は環境変数が未設定または空文字なら既定値を返し、それ以外は `std::atoi()` で整数化します。読み取り箇所では結果を 1〜8 に clamp します。

| 入力 | `split_` の値 |
|---|---:|
| 未設定または空文字 | 1 |
| `2`, `  +2tail` など `atoi()` が 2 と変換する値 | 2 |
| 数字で始まらない文字列（例: `abc`） | 1（`atoi()` の結果 0 を下限 clamp） |
| 0 または負数 | 1 |
| 1〜8 の整数 | その整数 |
| 8 より大きい整数 | 8 |

文字列全体の妥当性は検証せず、`atoi()` が数値として読める先頭部分を使います。たとえば `3tail` は 3 になります。大文字小文字は関係ありません。`atoi()` の範囲外入力に対する挙動は文書化された設定値として扱えません。

## 有効になる条件

この値は Metal backend の `ExpertStream::open()` が呼ばれたときに読み込まれます。`MetalWindow::open()` は固定 geometry（Qwen3.8-Flash-Next の 48 layer 構成）を検査し、`ExpertStream::wanted()` が true の場合に限って `ExpertStream` を生成して開きます。streaming は `STRATA_METAL_STREAM=1` の明示指定、または auto 判定で expert 群が GPU working set に収まらない場合に選ばれます。したがって、streaming を使わない実行では `STRATA_METAL_READ_SPLIT` は読み込まれません。

## 実行時の詳細

変数は stream object の open 時に一度読み込まれ、`split_` に保存されます。同じ object の実行中に環境を変更しても piece 数は変化しません。明示的な環境変数の継承・上書きはこの実装にはありません。

`.experts` 連続コピーが利用できる場合は expert 全体（gate、up、down を連結した領域）を `split_` 個に分けます。GGUF 本体から読む場合は gate、up、down の各 tensor slice をそれぞれ `split_` 個に分けるため、expert あたりの job 数は `3 * split_` です。分割境界は 4096 byte 単位に丸められ、最後の piece は残り全体を含みます。各 piece は I/O worker queue に送られ、全 piece の完了後に expert の slot を ready にします。

実際の同時実行数は `STRATA_METAL_IO_THREADS` による worker 数にも制限されます（未設定時 6、1 未満は少なくとも 1 worker）。この値は read の分割数であり、worker 数そのものではありません。stream arena のログは I/O worker 数と prefetch 数を表示しますが、`split_` の値を直接ログ出力する箇所は確認できません。

## 根拠

- `metal/src/engine/stream.cpp:27-30` — env helper。unset/空文字時の既定値と `atoi()` 変換。
- `metal/src/engine/stream.cpp:149-150` — worker 数と分割数の読み込み、および 1〜8 clamp。
- `metal/src/engine/window.cpp:440-457` — geometry 検査と streaming 条件、stream object の生成。
- `metal/src/engine/stream.cpp:272-304` — piece の単位、4 KiB 境界、実際の `pread()`。
- `metal/src/engine/stream.cpp:307-332,335-346` — I/O worker の job 処理と expert あたりの piece 数。
- `metal/src/engine/stream.cpp:481-482,541-544` — I/O worker 起動と表示される stream 統計。

`docs/MAC.md` の環境変数一覧には `STRATA_METAL_READ_SPLIT` の説明がなく、性能測定値も確認できなかったため、速度や推奨値は記載していません。
