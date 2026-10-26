# `DS4_STORE_ZC_FRAC`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

DeepSeek-V4.1 の RAM expert store が GPU から読めるようにマップされているとき、store 内の expert のうち GPU に公開するものを固定ハッシュで選ぶしきい値を指定する。既定値は `50`。この変数だけではゼロコピーを有効にしない。GPU への公開は別変数 `DS4_STORE_ZC` が有効で、かつ store と GPU マッピングが成立した経路で行われる。

## 値と判定

| 環境変数の状態・値 | `cfg.vis_percent` | 選択結果 |
| --- | ---: | --- |
| 未設定 | 50 | ハッシュ値 0〜49 の expert が公開候補 |
| `0` または負数 | 指定した整数 | ハッシュ値は 0〜99 なので公開候補なし |
| `1`〜`99` | 指定した整数 | ハッシュ値がその値未満の expert が公開候補 |
| `100` 以上 | 指定した整数 | ハッシュ値 0〜99 の全てが公開候補 |
| 空文字、数値として読めない文字列 | 0 | 公開候補なし |

設定値は `std::atoi` で `int` に変換される。したがって、先頭の空白と符号は変換規則に従い、数字の後ろに続く文字列は判定されない（例: `50junk` は 50、`junk50` は 0）。文字列全体の厳密な検証や範囲への clamp はない。整数として扱えないほど大きい入力の結果は保証されない。

## 有効になる条件

- `init_store()` が RAM store を作る必要がある。store の予算が正で、expert 層があり、先頭層の形式が MXFP4 で、expert がファイル上に置かれている場合に限り初期化へ進む。
- `DS4_STORE_ZC` が設定され、`atoi` の結果が 0 以外で、CUDA/HIP runtime から見える device が1つ、かつ `L[0].nm == 1` のときだけ GPU マッピングを要求する。複数 GPU 等では `DS4_STORE_ZC_FRAC` の値を読んでいても公開経路は作られない。
- GPU 用の arena マッピングが失敗した場合はゼロコピーを停止し、stderr に `ds4: RAM store: the arena could not be mapped for the GPU: zero-copy off` を出す。`DS4_STORE_ZC_FRAC` はこの失敗を変えない。
- 値は `ExpertStore::Cfg` に設定されるが、GPU 用 device address があり、expert が VRAM に載っておらず、slot が ready・非 pinned・非 prefetch である場合にだけ、同期時の公開判定に使われる。

## 実行時の詳細

モデル読み込み時に `init_store()` が store の初期化条件を通過すると、`DS4_STORE_ZC_FRAC` を一度読み、未設定なら `50` を `cfg.vis_percent` に入れる。プロセス起動後に環境を変更してもこの設定値は読み直されない。CLI のキャッシュ容量指定や `DS4_STORE_GB` は store の容量決定には関与するが、この割合を上書きするコードはない。

`ExpertStore::sync()` は window 境界で ready slot を調べる。候補の expert について `vis_hash(layer, expert)` を計算し、その値が `cfg.vis_percent` 未満なら device address を GPU 側の expert table へ公開する。ハッシュは `((unsigned)layer * 2654435761u + (unsigned)expert * 40503u) >> 7` を 100 で剰余した値で、0〜99 の範囲。選択は全体の正確な割合を保証するサンプリングではなく、このハッシュ値としきい値の比較で決まる。

公開 slot は store の空き枠を保つために同期時に回収されることがある。回収・公開イベントに応じてモデル側が層ごとの device table を更新し、decode の token 経路がその table を使って store の expert を扱う。したがって設定値は「store 中の全 expert を GPU に割り当てる割合」ではなく、公開可能な expert をハッシュでふるい分ける条件であり、実際の同時公開数は ready slot、VRAM 配置、pin 状態、store の reserve にも左右される。

`docs/DETAILS.md` の `STRATA_COLD_OVERLAP` の説明（267行目）にも “Zero-copy” が出るが、これはファイルの page-cache mapping を使う別経路であり、`DS4_STORE_ZC_FRAC` の仕様根拠ではない。DS4 の本変数について性能値や測定結果を示す記述は、確認した資料にはない。

## 根拠

- `src/dsv41/ds4_model.cu:2821-2822` — モデル読み込み中の `init_store()` 呼び出しと preload。
- `src/dsv41/ds4_model.cu:4633-4635` — store 初期化の容量・形式・ファイル配置条件。
- `src/dsv41/ds4_model.cu:4657-4669` — `DS4_STORE_ZC_FRAC` の `atoi`、既定値50、および GPU マッピングの要求条件。
- `src/dsv41/ds4_model.cu:4721-4745` — store の初期化結果、マッピング失敗時のログ、成功時のゼロコピー経路設定。
- `src/dsv41/ds4_store.hpp:69-70` — `vis_percent` の用途。
- `src/dsv41/ds4_store.hpp:286-330` — 同期時の公開条件と reserve slot を保つ回収処理。
- `src/dsv41/ds4_store.hpp:403` — 0〜99 の固定ハッシュ。
- `src/dsv41/ds4_model.cu:4800-4824` — 同期イベントを層別 device table に反映。
- `src/dsv41/ds4_model.cu:9089-9092`、`src/dsv41/ds4_kernels.cu:1880-1902` — decode token 経路で公開された store slot を使う staging 処理。
- `docs/DETAILS.md:267` — 文書との照合対象。説明されているのは別の page-cache zero-copy 経路。
