# `DS4_DBG_EG`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

DeepSeek-V4.1 の Engram 処理にある診断出力を有効にします。Engram 行のブロックスケール値と、dequant 後の `eg_x`、線形変換後の `eg_kv`、gate 適用後の残差 `h` を調べ、非有限値などを stderr に出します。環境変数は計算方式や値を選ぶ設定ではなく、診断コードの実行を切り替えます。

この確認が有効なのは `STRATA_METAL` が定義された Metal ビルドです。CUDA/HIP 向け `ds4_launch.h` では同じ helper が常に `false` を返すため、環境変数は読み取られず診断も有効になりません。

## 値と判定

`ds4_dbg("DS4_DBG_EG")` は `std::getenv(name) != nullptr` で判定します。値の文字列や数値は parse しません。

| 環境の状態 | Metal (`STRATA_METAL`) | CUDA/HIP など Metal 以外 |
|---|---|---|
| 未設定 | 無効 | 無効（helper が定数 `false`） |
| 空文字を設定 | 有効 | 無効（環境値を参照しない） |
| 任意の非空文字列 | 有効 | 無効（環境値を参照しない） |

したがって `0`、`false` を含む文字列も Metal では「設定済み」として有効です。数値範囲、大小文字、前後の空白、無効値からの fallback はありません。CLI 引数や別環境変数による上書きも、この実装にはありません。

## 有効になる条件

- Metal ビルドでは `ds4_launch.h` が `STRATA_METAL` 定義時に環境変数を調べる実装を選びます。Metal の CMake 設定は DeepSeek のソースを `strata_ds4` に含め、同ターゲットへ `STRATA_METAL=1` を付けます。
- 対象コードは DeepSeek-V4.1 のモデル実装 `src/dsv41/ds4_model.cu` にあります。Engram 分岐 (`l.eg >= 0`) を通る層でのみ `eg_x`、`eg_kv`、gate 後の `h` の診断が走ります。
- 読み込んだ行の scale 診断には追加で `pk.eg_hd >= 32` が必要です。
- CUDA/HIP 側では helper がコンパイル時定数 `false` です。CMake の通常 `strata-dsv41` は `STRATA_METAL` を付けず、また `STRATA_BUILD_DSV41` の既定値は OFF です。

## 実行時の詳細

値は `ds4_dbg()` 呼び出しごとに `getenv` で確認され、static cache には保存されません。対象ソースの参照箇所は `src/dsv41/ds4_model.cu` の 6372、10024、10039、10045 行です。プロセス起動後の環境変更を含め、各呼び出し時に見える環境状態が使われます。

1. Engram 読み込み batch の完了時、`eg_finish()` は各行の先頭 16 bit を調べます。`pk.eg_hd >= 32` の場合に限り、指数部が全 1 (`(hb & 0x7c00) == 0x7c00`) の値を見つけると stderr に `DBG eg bad scale: ...` を出します。このチェックは `DS4_DBG_EG` が設定されている場合だけです。
2. Engram 行の dequant 後、`eg_x` 全体を `dbg_nf()` で走査して `DBG nf il=... eg_x ...` を出します。さらに非有限要素があれば最初の該当要素を見つけ、`DBG eg bad x: ...` とその行の host/device byte を出して走査を止めます。
3. `eg_wkv` の計算後には同様に `eg_kv` の非有限値集計、Engram gate 適用後には `h_after_gate` の非有限値集計を出します。

`dbg_nf()` の出力には要素数、非有限値数、最初の位置、有限値の最大絶対値が含まれます。これらのログを出すためにバッファを読み走査しますが、環境変数による計算結果の置換、エラー終了、fallback の分岐は確認できませんでした。Engram 入力行そのものの読み取り失敗時に出る `ds4: WARNING: an Engram row could not be read ...` は `DS4_DBG_EG` の条件外であり、Metal では別途 stderr に出ます。

## 根拠

- `src/dsv41/ds4_launch.h:30-36`: Metal では `getenv(name) != nullptr`、Metal 以外は常に false。
- `metal/CMakeLists.txt:135-142,165-170`: DeepSeek ソースを `strata_ds4` に含め、同ターゲットに `STRATA_METAL=1` を設定。
- `CMakeLists.txt:906-920`: CUDA/HIP 系 `strata-dsv41` の構成と `STRATA_BUILD_DSV41` の既定 OFF。
- `src/dsv41/ds4_model.cu:6359-6383`: 読み込み batch 後の scale 診断と stderr 文言。
- `src/dsv41/ds4_model.cu:9758-9765`: `dbg_nf()` の走査と stderr 出力形式。
- `src/dsv41/ds4_model.cu:10008-10045`: Engram 層の判定、dequant 後・変換後・gate 後の診断箇所。
- `docs/DETAILS.md` と `docs/DEEPSEEK_MAC.md` を確認しましたが、`DS4_DBG_EG` の個別説明は見つかりませんでした。
