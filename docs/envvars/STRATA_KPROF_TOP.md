# `STRATA_KPROF_TOP`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

SYCL カーネルプロファイラが stderr に出す各 phase の集計表で、表示するカーネル起動箇所（site）の最大行数を指定します。計測自体を有効化する変数ではありません。プロファイラを有効にする `STRATA_KPROF` が必要です。

## 値と判定

`report_locked()` 内の関数ローカル `static const int` として、初回レポート生成時に一度読みます。未設定なら 45、設定済みなら `std::atoi()` の戻り値をそのまま使います。文字列全体の検証、エラー判定、範囲制限、負値の clamp はありません。

| 環境値 | 表示行数への効果 |
|---|---|
| 未設定 | 既定値 45 行 |
| `0`、空文字、先頭が数値として解釈できない文字列 | `atoi` が 0 を返し、site 行を表示しない |
| 正の整数 `N` | 時間の大きい順に最大 `N` 行 |
| 負の整数 | 最初の候補でもカウンタ `k` が値を超えるため、site 行を表示しない |
| 数字の後ろに文字が続く値 | `atoi` が先頭の数値部分を変換するため、その数値が上限になる（例: `12xyz` は 12） |

`atoi` のため、先頭の空白や符号は数値変換の規則に従います。`int` に収まらない数値について実装は検出・処理しておらず、ソースから安全な境界値動作は保証できません。phase の概要行は site 行数とは別に出力されます。

## 有効になる条件

- この読み取りは SYCL backend の `sycl/include/strata/kprof.hpp` に実装されています。通常の CUDA/HIP/Metal 経路には、この名前を読む実装は見つかりません。SYCL backend 自体は `STRATA_ENABLE_SYCL` による別ビルドです。
- プロファイラが有効でなければレポート生成に至りません。`STRATA_KPROF` は unset なら無効、設定時は先頭文字が `0` でない限り有効です。空文字も設定済みとして有効です。
- decode の per-kernel 計測は eager 経路を前提とします。SYCL コードの注釈では graph replay はイベントを記録せず、`STRATA_VERIFY_EAGER=1` で eager decode を実行するよう案内されています。prompt 側は eager launch とされています。
- `STRATA_KPROF_TOP` を有効にする別の CLI 引数や優先順位はありません。これは既定値 45 を上書きする表示上限です。

## 実行時の詳細

`report_locked()` は phase ごとに集計済みの site を所要時間の降順に並べ、ループ中の件数 `k` が `top` より大きくなった時点で表示を止めます。環境値はこのレポートが最初に作られるときにキャッシュされるため、その後プロセス内で環境を変更しても再評価されません。

レポートは、通常 `State` の破棄時に stderr へ出ます。また `STRATA_KPROF_EVERY` が正数なら、その値で指定した flush ごとにも stderr に出力されます。`STRATA_KPROF_TOP` 自体はログや終了状態を変えず、表示行数だけを変えます。SYCL event の読み戻しや計測の有効化は別の `STRATA_KPROF` 経路で行われます。

## 根拠

- `sycl/include/strata/kprof.hpp:118-139` — `STRATA_KPROF_TOP` の読み取りと既定値 45、site の降順ソート、上限判定。
- `sycl/include/strata/kprof.hpp:31-34` — `STRATA_KPROF` の読み取りと有効判定、結果の static cache。
- `sycl/include/strata/kprof.hpp:183-186,215-220` — `STRATA_KPROF_EVERY` による定期出力と終了時レポート。
- `sycl/include/strata/kprof.hpp:1-14` — SYCL プロファイラの説明、graph replay と eager decode / prompt に関する注釈。
- `sycl/include/dpct/device.hpp:685-699` — `STRATA_KPROF` 有効時の SYCL queue profiling 設定。
- `sycl/src/core/verify.cpp:2107-2111,2515-2529` — decode phase と window 終了時の計測処理、eager 条件の説明。
- `CMakeLists.txt:12-20` — SYCL backend は `STRATA_ENABLE_SYCL` で有効にする別 backend。
