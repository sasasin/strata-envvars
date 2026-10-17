# `STRATA_PIPE_BYIELD_NODRAIN`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。Strata 所有ソースを対象とし、外部ライブラリの環境変数は対象外。

## 役割

layer split の `--batch` で複数 slot group を stage 間にパイプライン実行しているとき、メインループに届いた `BYIELD` 行の前で、実行中の group を drain（すべて完了するまで pump）するかを制御します。既定では `BYIELD` も他の通常行と同じように drain します。有効にすると、この行の前の drain を省略し、行自体は通常どおり破棄します。

この変数は `BYIELD` を発生させたり、prompt の park / resume を設定したりするものではありません。また、他の行の drain を省略するものでもありません。

## 値と判定

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 有効（設定値の先頭文字 `v[0]` は `\0` であり、`'0'` ではない） |
| 先頭文字が `0` の文字列（例: `0`, `0abc`） | 無効 |
| それ以外の設定文字列（例: `1`, `-1`, `true`, `false`, 空白で始まる文字列） | 有効 |

数値変換や文字列全体の比較はせず、`getenv()` の結果が非 null で、先頭文字が `0` 以外かだけを判定します。大文字小文字や後続文字は判定に影響しません。

## 有効になる条件

値が有効でも、メインループ内で `piped` が true の場合に限って効果があります。実装上の `piped` は `--batch` が正数、`--batch-groups` が 1 より大きく、layer split の stage 数 `n_pipe` が 1 より大きい場合に true です。さらに、そのループで batch slot が稼働中か、pipeline group が in-flight であるため、入力行を処理する分岐に入る必要があります。

その分岐で `BSTOP ` 以外の行を処理するときに環境値を参照し、行が `BYIELD` で始まる場合だけ drain を抑制します。したがって、`BGEN` など別の行では値が有効でも drain されます。`BYIELD` 行もこの分岐より前にある入力待ち・pump の動作を変更しません。

## 実行時の詳細

判定関数 `pipe_byield_nodrain_env()` は関数内の `static const bool` に結果を保存します。初回評価はプロセス起動時ではなく、pipelined batch の入力行処理で `BSTOP ` 以外の行が来て、この関数が呼ばれた時です。その後にプロセス環境を書き換えても再評価されません。CLI、設定ファイル、別環境変数による上書きはこの実装にはありません。

メインループでは `piped` かつ `BSTOP ` 以外で、`STRATA_PIPE_BYIELD_NODRAIN` が有効かつ行が `BYIELD` で始まる、という条件のときだけ `pipe_drain()` を呼ぶ条件を外します。その後、`BYIELD` で始まる行は `continue` で破棄されます。つまり有効時は、BYIELD の処理を待つためだけに残っている pipeline group があっても、その完了を待たずにメインループへ戻ります。

この制御はメインループ直前の drain に限られます。たとえば `STRATA_PIPED_CONCURRENT` の prompt read 経路には、BYIELD 要求を検知した後に `pipe_drain()` を呼ぶ別の処理があります。この環境変数はその呼び出しを変更しません。

trace が有効で piped path の場合、BYIELD 処理では stderr に `strata trace: BYIELD dropped, %d groups in flight` が出ます。通常の drain が実行される経路では、trace に drain 時間も記録されます。この変数自体の専用ログはありません。

## 根拠

- 値の読み取り、`getenv` 判定、static cache: `src/program/generate.cpp:169-178`。
- piped batch の成立条件: `src/program/generate.cpp:11092-11099`。
- メインループで BYIELD 前の drain を省略する条件、および BYIELD 行の破棄と trace: `src/program/generate.cpp:11272-11316`。
- BYIELD が prompt read の途中で短い request に道を譲る制御行であること: `src/program/generate.cpp:12751-12756`。
- concurrent prompt read の BYIELD 検知後にも別個の drain があること: `src/program/generate.cpp:13065-13085`。
- 関連資料も pipelined batch の BYIELD 前 drain を省く switch と説明: `docs/BATCHING.md:110-121`。`docs/DETAILS.md` にはこの変数の個別説明は見つからず、性能測定値は本調査では確認できない。
