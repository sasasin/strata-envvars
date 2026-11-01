# `GPU_PINNED_MIN_XFER_SIZE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Strata はこの名前の環境変数を自分の処理設定として読み取りません。Linux の HIP 系ビルドで `STRATA_ARENA_MMAP` が有効なとき、プロセス起動時に既定値 `1000000` を環境へ追加します。既に同名の環境変数があればその値を上書きしません。変数名は Strata のソースでこの設定箇所にのみ現れ、実行時の効果は外部コンポーネント側のため、ここでは説明しません。

## 値と判定

| 状態 | Strata の処理 |
| --- | --- |
| `STRATA_ARENA_MMAP` が未設定 | `GPU_PINNED_MIN_XFER_SIZE` を設定しない |
| `STRATA_ARENA_MMAP` が空文字、または先頭文字が `1` 以外 | 設定しない |
| `STRATA_ARENA_MMAP` の先頭文字が `1` | `setenv("GPU_PINNED_MIN_XFER_SIZE", "1000000", 0)` を呼ぶ |
| `GPU_PINNED_MIN_XFER_SIZE` が既に設定済み | `setenv` の overwrite 引数が `0` のため、既存値を維持する。空文字も設定済みとして扱われる |
| `GPU_PINNED_MIN_XFER_SIZE` が未設定 | 値 `1000000` を設定する |

`STRATA_ARENA_MMAP` は文字列全体を parse せず、先頭文字だけを `'1'` と比較します。したがって `1`, `10`, `1anything` は条件を満たし、`true`, `01`, 空文字は満たしません。対象変数自体について、Strata は既存値を数値変換・検証せず、境界値や無効値の判定もしません。設定 API の戻り値も確認していません。根拠: `src/program/generate.cpp:2940-2941`, `sycl/src/program/generate.cpp:1761-1762`。

## 有効になる条件

- `STRATA_USE_HIP` または `STRATA_HIP_GFX906` のいずれかが定義されたビルドであること。
- `_WIN32` が定義されていないこと。
- `STRATA_ARENA_MMAP` の値があり、先頭文字が `1` であること。

この条件は CLI の `--mmap-experts` ではなく `STRATA_ARENA_MMAP` で判定されます。対象変数の設定箇所は `main()` の引数解析より前にあり、`--version` / `-V` はその手前で終了するため、その呼び出しでは設定箇所に到達しません。`STRATA_ARENA_MMAP` 自体はファイルバックの expert arena に関係する別設定です（`src/core/expert_source.cpp:5816-5825`; SYCL 側 `sycl/src/core/expert_source.cpp:3350-3359`）。

## 実行時の詳細

通常の起動では引数解析前に一度だけ `STRATA_ARENA_MMAP` を読み、条件成立時に対象変数の既定値を設定します。対象変数の値を Strata が後から読み直す処理、CLI 引数や別設定との優先順位判定、ログ・警告・終了分岐は確認できませんでした。設定呼び出しの失敗も明示的には処理されません。

候補一覧と関連ドキュメントには同名の記載がありますが、役割は異なります。`docs/AMD_HIP.md:372-377` は ROCm 7.2.4 の RX 6800 でサーバー JSON の `env` に `1048576` を指定した報告例を載せ、`docs/TROUBLESHOOTING.md:344-347` も同報告に触れています。これらは利用者が設定する回避策の記録です。Strata のコードが設定する値は `1000000` であり、Strata はこの値を解釈しないため、文書中の値の違いから外部側の意味や効果は推定しません。

## 根拠

- HIP 系・非 Windows の条件、`STRATA_ARENA_MMAP` の先頭文字判定と既定値設定: `src/program/generate.cpp:2934-2942`, `sycl/src/program/generate.cpp:1755-1763`。
- `--version` / `-V` が設定箇所より先に return すること: `src/program/generate.cpp:2918-2932`, `sycl/src/program/generate.cpp:1746-1753`。
- `STRATA_ARENA_MMAP` の関連する file-backed arena 実装: `src/core/expert_source.cpp:5816-5848`, `sycl/src/core/expert_source.cpp:3350-3381`。
- 手動設定例: `docs/AMD_HIP.md:365-379`, `docs/TROUBLESHOOTING.md:341-347`。
