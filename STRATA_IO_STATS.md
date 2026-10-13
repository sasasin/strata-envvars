# `STRATA_IO_STATS`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

`--mmap-experts` で使うファイル層について、expert blob を読む時点で各ページがページキャッシュに載っていたバイト数と、載っていなかったバイト数を集計し、実行時の I/O レポートに含めます。値を有効にしても読み取り方式や expert の選択は変更しません。Linux では計測に `mincore` を使います。

## 値と判定

`src/program/generate.cpp` のファイル層初期化で `std::getenv("STRATA_IO_STATS")` を1回評価します。未設定なら何もしません。設定されている場合は `std::atoi` の結果が 0 以外なら統計を有効にします。

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字、`0`、`false`、数字で始まらない文字列 | `atoi` が 0 を返すため無効 |
| `1`、`-1`、`2tail`、先頭の空白の後に非ゼロ数値がある文字列 | `atoi` が非ゼロを返すため有効 |

文字列全体の比較や厳密な数値検証は行いません。`STRATA_IO_PREFETCH` が `atoi` で非ゼロと判定されると、その分岐が先に選ばれるため、この変数単独での判定は行いません。prefetch 自体が統計を有効にします。

## 有効になる条件

- `--mmap-experts` を指定し、`FileExpertSource` を開く経路でのみ、この変数を読みます。既定の resident arena 経路には適用されません。
- `STRATA_IO_PREFETCH` が未設定または `atoi` で 0 の場合に限り、この変数の値が判定されます。prefetch が有効な場合は `set_io_prefetch()` が `io_stats_` も有効にします。
- 実際のページ常駐計測とカウンター加算は `__linux__` のコードにあります。Windows など Linux 以外では `set_io_stats(true)` が呼ばれてレポート分岐に入る場合がありますが、ここで説明する `mincore` 計測は実行されず、これらのカウンターは増えません。
- unbuffered 読み取りが成功すると `copy_from_files()` は直接読み取りの後に戻るため、その blob はこのページキャッシュ計測の対象になりません。直接読み取りが失敗して mmap へ fallback した場合は mmap 側の計測経路に進みます。

## 実行時の詳細

初期化時に条件を満たすと `src.set_io_stats(true)` を呼びます。これは `io_stats_` を立てるだけです。Linux の `FileExpertSource::copy_from_files()` はファイル層から blob を渡す際、blob の各 span について `resident_in()` を呼び、常駐バイトと非常駐バイトを atomic counter に加算します。prefetch が無効なら、この分岐はページ常駐の計測と通常の mmap からのコピーを行い、`pread` への切り替えはしません。ヘッダーの説明ではこのチェックは blob ごとに数マイクロ秒かかるとされています。

serve 経路では、`/proc/self/io` のサンプルが有効なリクエストについて stderr の `file tier I/O this request` 行に、前回サンプルからのページキャッシュ常駐／非常駐バイトを追加します。通常の generate の終了レポートでは stdout の `io path` 行に累積値を出します。いずれも Strata の診断出力です。環境変数は初期化時に一度だけ調べるため、起動後に値を変更しても反映されません。

## 文書との照合

`docs/DETAILS.md` は `STRATA_IO_STATS=1`（または prefetch 有効時）に `mincore` によるページキャッシュの hit/miss 分割が加わると説明しており、実装と一致します。同節の性能測定は `STRATA_IO_PF_STAGE` の比較であり、`STRATA_IO_STATS` 自体の性能効果を測定した値ではありません。

## 根拠

- `src/program/generate.cpp:4622-4637`: `--mmap-experts` の `FileExpertSource` 初期化経路。
- `src/program/generate.cpp:4667-4698`: `STRATA_IO_PREFETCH` を先に判定し、それ以外で `STRATA_IO_STATS` を `atoi` 判定する箇所。
- `include/strata/core/expert_source.hpp:717-732,824-839`: I/O 経路、統計 setter、既定値とカウンター。
- `src/core/expert_source.cpp:636-669`: prefetch 設定時に `io_stats_` も有効化する処理。
- `src/core/expert_source.cpp:1185-1214`: direct read の早期 return と Linux のページ常駐カウント。
- `src/program/generate.cpp:12308-12339,13213-13232`: serve のリクエスト単位ログと generate の終了レポート。
- `docs/DETAILS.md:225-232`: Linux file-tier I/O path の説明。
