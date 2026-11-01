# `HF_TOKEN`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`HF_TOKEN` は `tools/trellis/hf_slice.py` が Hugging Face 上の safetensors リポジトリへ HTTP 要求を送るとき、任意の `Authorization: Bearer ...` 要求ヘッダーを付けるために使います。Strata のエンジン、CLI、サーバーの設定ではなく、Trellis の研究・検証用データ取得スクリプトに使われる値です。`tools/trellis/README.md:18-19` は `hf_slice.py` をエンコーダの検証用ファイルとして列挙し、同ファイル先頭の説明は公開リポジトリでは token 不要、gated repository では `HF_TOKEN` を環境に設定すると記しています（`tools/trellis/hf_slice.py:1-7`）。

## 値と判定

| 環境の状態 | Strata の処理 |
|---|---|
| 未設定 | `os.environ.get()` が `None` を返し、Authorization ヘッダーを追加しない |
| 空文字 | 空文字は偽として扱われ、Authorization ヘッダーを追加しない |
| 非空文字列 | 文字列を変換・検証せず、`Bearer ` に連結して Authorization ヘッダーに設定する |

数値変換、真偽値文字列の解析、空白の trim、長さや文字種の検査はありません。したがって空白だけの値も非空としてヘッダーに使われます。既定の token 値はありません。CLI 引数や他の環境変数との優先順位もありません（`tools/trellis/hf_slice.py:23-31`）。

## 有効になる条件

- `tools/trellis/hf_slice.py` の `_get()` が実行される取得経路に限ります。主な呼び出し元は、原本テンソルの取得スクリプト `fetch_orig.py` と、Gyro 重み比較・誤差分析スクリプトです（`tools/trellis/fetch_orig.py:17,30,53`; `tools/trellis/gyro_vs_original.py:25-27,59,67-68`; `tools/trellis/gyro_column_profile.py:17-19,39,43-44`; `tools/trellis/gyro_error_profile.py:20-22,43,47-48`）。
- OS、GPU backend、ビルド macro、モデル実行状態による分岐はありません。これらの Python ツールが HTTP 要求を行うとき、プロセスの環境に値があれば使います。
- Strata 側では token の有効性や権限を検査しません。認証の成否を決める外部サービス側の挙動は本調査の対象外です。

## 実行時の詳細

`_get(url, start, end)` は要求を作成するたびに `HF_TOKEN` を読み直します。プロセス起動時のキャッシュはなく、呼び出し時点の環境値が使われます。値が非空なら Authorization ヘッダーを設定し、`start` が指定されている場合は別途 Range ヘッダーも設定してから、`urllib.request.urlopen(..., timeout=120)` を呼びます（`tools/trellis/hf_slice.py:23-31`）。コードは token を出力しません。

`Repo` は初期化時に index を取得し、必要な safetensors shard header を shard ごとに `_hdr` にキャッシュしますが、token 自体はキャッシュしません。テンソル範囲の取得は `_get()` / `get_parallel()` に戻るため、その要求ごとに環境値を読みます（`tools/trellis/hf_slice.py:34-50,58-70,77-94`）。単一範囲の `get_parallel()` は `_get()` を直接呼びます。複数範囲では各範囲要求を最大 6 回試し、最後も例外なら再送出します。単一範囲経路や index/header 要求にはこの再試行ループは適用されません（同:34-50,62,67-69）。

HTTP 要求で発生した例外は `_get()` 内で捕捉・変換されません。複数範囲の再試行を使い切った場合も例外が呼び出し元へ伝播します。ここに専用の警告文、エラー処理、終了コード変換はありません。スクリプトのトップレベルから呼ばれた場合、未処理例外として Python が終了を報告します。

## 根拠

- 唯一の直接読み取りとヘッダー設定: `tools/trellis/hf_slice.py:23-31`。
- 取得の再試行、HTTP タイムアウト、index/header/tensor 取得と header cache: `tools/trellis/hf_slice.py:30-31,34-50,58-70,77-94`。
- 同梱ツール内であることと利用スクリプト: `tools/trellis/README.md:18-19`; `tools/trellis/fetch_orig.py:17,30,53`; `tools/trellis/gyro_vs_original.py:25-27,59,67-68`; `tools/trellis/gyro_column_profile.py:17-19,39,43-44`; `tools/trellis/gyro_error_profile.py:20-22,43,47-48`。
