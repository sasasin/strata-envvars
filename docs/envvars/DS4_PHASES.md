# `DS4_PHASES`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

DeepSeek-V4.1（DS4）エンジンの host-routed layer 実行で、token 単位の呼び出し時間を4区間に分けて集計し、プロセス終了時に標準エラーへ出す診断フックです。区間計測の有効化だけを行い、ルーティングや expert の選択・計算経路を切り替えません。

この環境変数の名前を直接渡す箇所は `src/dsv41/ds4_model.cu:10418` の1箇所です。そこで共通診断 helper `ds4_dbg` を呼びます。helper は `STRATA_METAL` 定義時に `std::getenv(name) != nullptr` を返し、それ以外では常に `false` を返すため、環境値を読むのは Metal ビルドのみです（`src/dsv41/ds4_launch.h:30-36`）。

## 値と判定

| ビルド／値 | 判定 |
|---|---|
| Metal: 未設定 | 無効 |
| Metal: 空文字を含む任意の設定値 | 有効。値の内容は変換・比較しない |
| CUDA / HIP など Metal 以外 | 常に無効。helper が `constexpr false` を返す |

数値変換、大小文字比較、空白処理、範囲検査、無効値時の fallback はありません。したがって `DS4_PHASES=0` や空文字も、Metal では「設定あり」として有効です。CLI 引数や別の環境変数との優先順位はありません。

## 有効になる条件

- `strata-dsv41` の DS4 エンジンを含むビルドであること。CMake では `STRATA_BUILD_DSV41` が既定 OFF で、ON かつ `STRATA_HIP_GFX906` でない場合に同実行ファイルを追加します（`CMakeLists.txt:906-920`）。
- `STRATA_METAL` 定義のあるビルドであること。CUDA/HIP 側では `ds4_dbg` が常に false なので、変数を設定しても集計されません（`src/dsv41/ds4_launch.h:30-36`）。
- `Impl::layer()` の host-routed 経路を通ること。先行する `wp.async` 経路は別処理をして成功 return するため対象外です。続く host-routed 経路では tensor parallel (`nm > 1`) はエラー return となり、この計測箇所に進みません（`src/dsv41/ds4_model.cu:9961-9968,10301-10418`）。
- 集計と出力にはさらに `T == 1` が必要です。`T` が複数行の呼び出しでは計測点の一部で時刻を取得しますが、合計カウンターを更新せず、終了時出力も登録しません（`src/dsv41/ds4_model.cu:10418-10420,10596-10600`）。

## 実行時の詳細

`phases` は `Impl::layer()` 内の function-local `static const bool` です。helper の環境参照はこの関数が初めて計測箇所まで到達した時に一度評価され、その後は値をキャッシュします。プロセス実行中に環境を変更しても反映されません。さらに、この初回評価は host-routed 経路に入った時点で起こります（`src/dsv41/ds4_model.cu:9961,10301-10420`）。

有効時、成功した `T == 1` の layer 呼び出しについて、次の区間を `now_ms()` で加算します（`src/dsv41/ds4_model.cu:10420-10421,10454-10457,10554,10591-10600`）。

1. `route enqueue + shared expert + wait`: `ph0` から GPU event 同期後の `ph2` まで。
2. `routing analysis + GPU experts enqueue`: `ph2` から expert の CPU 処理直前の `ph3` まで。
3. `CPU lane + combine + hc_post`: `ph3` から `hc_post` 後の `ph4` まで。
4. `attention enqueue`: 前回 layer の `ph4` から今回の `ph0` まで。ただし差が 5 ms 未満の場合だけ加算。

最初の3区間は `ph_n` 件で割った平均を、4区間目と併せて atexit handler が次の形式で `stderr` に出します: `phases per layer call (%ld): route enqueue + shared expert + wait %.3f ms, routing analysis + GPU experts enqueue %.3f ms, CPU lane + combine + hc_post %.3f ms, attention enqueue %.3f ms`。最初の成功した `T == 1` 呼び出し後に handler を登録します。計測対象呼び出しがエラーで途中 return し、登録に到達しない場合、この環境変数固有の出力はありません（`src/dsv41/ds4_model.cu:10426-10431,10539-10553,10591-10600`）。

`DS4_PHASES` 自体による警告、エラー終了、timeout 経路はありません。計測値を読むだけの診断であり、性能値・精度への効果を示す測定資料は確認できませんでした。`docs/DETAILS.md` にもこの名前の説明はありません。

## 根拠

- 環境変数名の直接参照と計測初期化: `src/dsv41/ds4_model.cu:10418-10420`
- helper の Metal／非 Metal の判定差: `src/dsv41/ds4_launch.h:30-36`
- `strata-dsv41` のビルド条件: `CMakeLists.txt:906-920`
- host-routed 処理と区間集計・終了時出力: `src/dsv41/ds4_model.cu:10301-10431,10454-10457,10554-10603`
