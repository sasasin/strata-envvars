# `STRATA_PIPELINE_SWITCH`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

`--serve` のパイプライン window を使う検証用スイッチファイルのパスを指定します。ファイルの内容から、各リクエストの prompt 読み取り方法と、decode 時の speculative pipeline の設定を上書きできます。これは通常の CLI オプションではなく、`STRATA_PIPELINE_DEBUG` が許可したときだけ使われるテスト／A/B 用フックです。

## 値と判定

| 条件 | 動作 |
|---|---|
| `STRATA_PIPELINE_DEBUG` が未設定、空文字、または先頭文字が `0` | 共通 helper はこの変数を未設定として返すため、スイッチファイルを開かない。 |
| `STRATA_PIPELINE_DEBUG` の先頭文字が `0` 以外 | `STRATA_PIPELINE_SWITCH` の値を参照する。`STRATA_PIPELINE_DEBUG` 自体は文字列全体や数値として parse しない。 |
| スイッチパスが未設定、またはパイプラインが有効でない | ファイル読み取りとスイッチログは行わず、CLI／既定値を使う。 |
| パスが設定され、パイプラインが有効で、ファイルを開ける | リクエストごとにファイル先頭から最大255 byteを読み、内容中にある設定項目を適用する。 |
| ファイルを開けない | 設定を適用せず、スイッチログも出さない。エラーにはしない。 |

ファイル内容は空白区切りの `pw=<0|1|2> theta=<f> force_miss=<k> short_read=<n>` 形式を想定します。実装は文字列全体を構文解析せず、各キーの最初の部分文字列を `strstr` で探し、その直後を `atoi`／`atof`／`atoll` で変換します。従って、区切り文字や数値の後ろの文字を厳密には検査しません。キーがなければその項目の現在値を維持します。

| 項目 | 値の変換・範囲 | ファイル項目がない場合 |
|---|---|---|
| `pw` | `atoi` の後、0〜2 に clamp。数値として読めない接尾部は `atoi` の規則に従う。 | `pipe` が真なら `--pipeline-windows` の実効値、偽なら0。 |
| `theta` | `atof` で `float` に変換。明示的な範囲制限なし。 | `STRATA_PIPELINE_THETA` が helper 経由で読めればその `atof` 値、なければ0.2。 |
| `force_miss` | `atoi` の後、0未満を0に clamp。 | `STRATA_PIPELINE_FORCE_MISS` が読めれば `max(0, atoi(...))`、なければ0。 |
| `short_read` | `atoll` の後、0未満を0に clamp。 | `--short-read` の値。 |

`STRATA_PIPELINE_THETA` と `STRATA_PIPELINE_FORCE_MISS` も `STRATA_PIPELINE_DEBUG` による gate の対象です。ファイルに `theta=` 等があれば、環境変数由来の値を上書きします。`pw` と `short_read` に対応する同名の環境変数はこの処理では読まず、CLI 値から開始します。

## 有効になる条件

- 値の参照には `STRATA_PIPELINE_DEBUG` が必要です。helper は最初に呼ばれた際の gate 判定を `static const bool` に保存するため、その後プロセス内で環境を書き換えても判定は変わりません。空文字は無効、先頭文字が `0` なら無効、`false` や `1anything` は有効です。
- スイッチファイルの処理は `pipe` が真のときだけです。これは `--pipeline-windows` が正値で、複数 GPU の layer split と stage 条件などを満たし、起動時の検証で無効化されていない場合に限られます。機能には `--serve`、少なくとも2 GPU の layer split、MTP drafter と `--spec` 2以上が必要です。batch slots、peer device、helper cache などの条件で無効になる場合があります。
- `pw=1` 以上は、対応する2-stage prompt verify-window 経路で `read_windows_pl` を選びます。`STRATA_LOGPOS` が設定されていると通常の serial window 読み取りに戻ります。
- `pw=2` は decode window の pipeline も要求しますが、CUDA/HIP では `pl_snap_ok`、SYCL では `pl_snap2[0] != nullptr` が必要です。さらに repetition penalty（`penalty_last_n`）や coupled draft sampling を使う要求は serial decode になります。これらの条件を満たさない場合、prompt 側に `pw=1` の効果が残ることはありますが、decode overlap は実行されません。

## 実行時の詳細

各リクエストで `pl_pw`、`pl_theta`、`pl_force_miss`、`req_short_read` を初期化した後、スイッチファイルを読みます。パス文字列は `static const char*` として最初に評価した値を保持しますが、ファイル自体は各リクエストで開き直して内容を読みます。したがって、起動後に環境変数のパスだけ変更しても反映されませんが、同じパスのファイル内容の変更は次のリクエストから読み取られます。ファイルを開いて読み取った場合は stderr に `strata pipeline switch: pw=%d theta=%.3f force_miss=%d short_read=%lld` を出します。

- `pw` は上記の prompt／decode pipeline 選択に使います。値は0〜2です。
- `theta` は speculative window の受理見込み確率 gate と比較され、pipeline 内で先行 window を進める条件に使われます。`atof` の結果に独自の範囲検査はありません。
- `force_miss=k`（k>0）は k 回ごとの speculative window で先頭 token を意図的に別値へ変え、rollback 経路を試します。これは通常生成の品質設定ではありません。
- `short_read=n` は prompt の区間を verify windows に通せる長さの上限を更新します。区間が n token を超える場合は batched prompt path 側になります。埋め込み行を含む区間や `STRATA_CKPT_REREAD` が有効な場合も verify windows 対象外です。`short_read=0` なら正の長さの区間は条件を満たしません。

CUDA/HIP 実装と SYCL 実装の双方に同じファイル形式、gate、値変換があります。pipeline decode の内部実装や snapshot 利用条件には backend 差があります。ファイルを読む実装は request loop 内にあり、設定値は当該リクエストのローカル変数に反映されます。子プロセスへの転送処理はこの読み取り箇所にはありません。

## 根拠

- gate helper と gate のキャッシュ: `src/program/generate.cpp:340-346`, `sycl/src/program/generate.cpp:296-301`。
- pipeline 起動条件と拒否時の stderr ログ: `src/program/generate.cpp:4204-4249`。実行時 `pipe` 判定: `src/program/generate.cpp:8864`。
- CUDA/HIP request-local defaults、ファイル読み取り、parse、stderr: `src/program/generate.cpp:12909-12948`。SYCL 同等箇所: `sycl/src/program/generate.cpp:10157-10191`。
- prompt window 選択と `STRATA_LOGPOS` 条件: `src/program/generate.cpp:13039-13044`, `sycl/src/program/generate.cpp:10280-10288`。
- decode pipeline gate、serial 条件、`theta`／`force_miss` の利用: `src/program/generate.cpp:14067-14113,14220,14484,14519`; SYCL: `sycl/src/program/generate.cpp:10763-10795,10931,11229,11253`。
