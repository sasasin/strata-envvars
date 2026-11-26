# `--ple-delay-us`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数。parser 内の usage 表記は `strata generate`） |
| オプション | `--ple-delay-us` |
| 別名 | なし |
| 値 | マイクロ秒単位の非負数（`double` として変換） |

## 役割

PLE（n-gram table）の行読み取り完了を意図的に遅らせる fault injection 用オプションです。ストレージの通常動作を指定する設定ではなく、PLE reader の遅延時の動作を調べる用途です。CUDA/HIP 系と SYCL 系の engine parser に実装があります。

## 使い方

```sh
strata --pack pack/full --tokens "1,2,3" --ple-delay-us 500
```

上例は、実際に PLE table の行読み取りが発生した場合、その読み取り完了を発行から最低 500 µs 保留します。モデルや pack に応じた通常の引数は別途必要です。

## 値と既定値

- 値は `std::atof` で `double` に変換されます。未指定時は `0` で、遅延注入は設定されません。正の値のときだけ reader に設定されます（`engine/src/program/generate.cpp:822,3904,6419`、SYCL: `engine/sycl/src/program/generate.cpp:506,1943,3487`）。
- `--ple-delay-us` の後ろに値がない場合、parser の共通 `next()` が stderr に `--ple-delay-us needs a value` を出して終了コード 2 で終了します（`engine/src/program/generate.cpp:3844-3846`、SYCL: `engine/sycl/src/program/generate.cpp:1884-1886`）。
- `atof` による変換で、整数専用ではなく小数値も指定できます。ただし入力全体の厳密な数値検査はありません。変換結果が負、または NaN なら PLE 関連オプションの validation に失敗し、stderr に `invalid --ple-io/--ple-row-cache/--ple-inflight/--ple-delay-us` を出して終了コード 2 になります（`engine/src/program/generate.cpp:5009-5012`、SYCL: `engine/sycl/src/program/generate.cpp:2517-2520`）。
- 同じオプションを複数回指定した場合の重複拒否処理はなく、引数ループで後の値が上書きします（`engine/src/program/generate.cpp:3842-3843,3904`、SYCL: `engine/sycl/src/program/generate.cpp:1881-1883,1943`）。

## 実行時の動作

parser は値を `Options::ple_delay_us` に格納します。PLE table を開いて engine session に配線する箇所で、値が `0` より大きければ `PleTable::set_injected_delay_us` に渡します（`engine/src/program/generate.cpp:6419-6420`、SYCL: `engine/sycl/src/program/generate.cpp:3487-3489`）。reader は読み取り発行時刻を記録し、ファイル読み取りが完了しても発行から指定時間に満たない場合は completion を保留し、経過後に処理します（`engine/src/ngram/ple_reader.cpp:158-166,264-280,285-296,606-609`。SYCL: `engine/sycl/src/ngram/ple_reader.cpp:268-284,289-300,558-561`）。

遅延を設定しても、読み取り自体を遅くするものではなく、完了済みの読み取り結果を reader 内で遅らせます。したがって PLE が有効で table の行読み取りが起きる経路に限って影響します。`--no-ple` で PLE を無効化する経路では table を開かず、遅延 setter も呼びません（`engine/src/program/generate.cpp:5155,5205-5213,6419`）。キャッシュヒットなど、ファイル行読み取りが生じない処理にもこの完了保留は適用されません（reader の保留対象は `file.wait` から返った completion: `engine/src/ngram/ple_reader.cpp:264-280`）。

## 適用条件と副作用

- 既定値の `0` は fault injection を行いません。正の値では読み取り結果の処理が遅れ、PLE を使う推論の待ち時間に影響し得ます。通常の設定・出力先・環境変数との優先順位はありません。
- 値は有限性の検査を受けず、validation は `value >= 0` のみです。そのため正の無限大は parser の条件を通過し得ます。reader の経過時間との比較では有限の経過時間が無限大以上にならず、保留 completion が解放されない可能性があります（`engine/src/program/generate.cpp:5009-5012`、`engine/src/ngram/ple_reader.cpp:285-294`）。無限大は指定しないでください。
- 明示的な範囲上限、単位変換、警告、出力ファイル生成は確認できませんでした。値の厳密な表記形式やプラットフォーム別の境界動作については、`atof` と validation の実装以上の保証を確認できません。

## 出力とエラー

無効値は前述の PLE 関連 validation エラーを stderr に出し、終了コード 2 で終了します。オプションが未知の引数として扱われた場合は `unknown argument: ...` と usage を stderr に出して終了コード 2 ですが、この revision では CUDA/HIP 系・SYCL 系の両 parser に登録されています（`engine/src/program/generate.cpp:4268-4273`、SYCL: `engine/sycl/src/program/generate.cpp:2214-2219`）。正の値による遅延専用の通知出力は確認できませんでした。

## 根拠

- `engine/src/program/generate.cpp:817-823,1225-1228,3901-3905` — CUDA/HIP 系の option default、usage、parser 登録。
- `engine/src/program/generate.cpp:3842-3846,5009-5012,6419-6420` — 値取得、validation、PLE table への適用。
- `engine/src/ngram/ple_reader.cpp:158-166,264-296,606-609` — 読み取り発行時刻、completion の保留と解放、setter。
- `engine/sycl/src/program/generate.cpp:501-507,810-816,1940-1944,2517-2520,3487-3489` — SYCL 系の default、usage、parser、validation、適用箇所。
- `engine/sycl/src/ngram/ple_reader.cpp:268-300,558-561` — SYCL reader の completion 保留と setter。
- `engine/src/program/generate.cpp:5155,5205-5213` — `--no-ple` 時の PLE 無効化経路。
