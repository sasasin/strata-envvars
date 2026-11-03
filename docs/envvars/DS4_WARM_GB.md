# `DS4_WARM_GB`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

DS4 のファイル読み出し経路で、プロンプト処理後にデコードが使いそうな expert のデータを、バックグラウンドスレッドから先読みする容量を GB 単位で指定します。先読み先は Strata の明示的な RAM tier ではなく、OS のファイル page cache です。変数を設定すると、通常は無効になる複数 GPU 構成でもこの先読み経路を許可します。

## 値と判定

| 状態 | 判定・動作 |
|---|---|
| 未設定・GPU 1 基 | `ram_avail()` が不明値なら既定 8 GB。既知なら `min(32, max(0, (利用可能 RAM - 8 GiB) / 2e9))` GB。計算上の margin は `8ull << 30` bytes。 |
| 未設定・GPU 複数基 | 先読みを開始せずに戻る。 |
| 設定あり | `std::atof` で `double` に変換し、上記既定値を置き換える。GPU 複数基でも設定の有無を通過条件に使う。 |
| 変換後が 0 以下 | 先読みしない。空文字や通常の非数値文字列は `atof` で 0 となるため、この経路では先読みしない。 |
| 変換後が正数 | 指定値を `1e9` 倍した byte 数を上限として先読みする。上限の clamp はない。数値の後ろに `atof` が変換しない文字があっても、先頭の数値部分が使われる。 |

`atof` の変換結果を全体文字列として検証しません。`nan` のように NaN となる入力は `gb <= 0` を通過し、`done >= budget` も成立しないため、停止要求がなければ候補リストを最後まで走査します。正の無限大も実質的に候補リスト全体を上限で止めません。通常の容量指定には有限の正数を使います。

## 有効になる条件

- `warm_after()` が呼ばれる DS4 プロンプト経路であること。
- `file_experts` が有効であること。GGUF ではこのフラグが常に立ちます。その他の pack では `--mmap-experts` 指定や RAM/VRAM の容量判定で決まります。
- `L` が空でなく、先頭 layer の形式が MXFP4 であること。
- プロンプトで処理した token 数 `n` が `DS4_WARM_MIN` 以上であること。`DS4_WARM_MIN` は未設定なら 512、設定時は `atoi` の結果で、初回 `warm_after()` 時に static cache されます。
- 複数 GPU なら `DS4_WARM_GB` が設定済みであること。空文字でも「設定済み」条件は通りますが、容量は 0 になり先読みされません。

`DS4_WARM_GB` に対する CLI 引数や別変数の優先順位はありません。変数の設定値は内部の RAM 量による既定容量を置き換えますが、`file_experts`、MXFP4、プロンプト長などの条件は引き続き適用されます。

## 実行時の詳細

`warm_after(took)` は prompt chunk 処理の末尾で、token/cache 状態を更新した後に呼ばれます。条件を満たすと、各 layer の `last_picks` から末尾 row 側を優先して expert を集め、同じ expert の重複、無効 index、VRAM slot にある expert、RAM tier にある expert を除外します。その順で専用スレッドが各 expert のファイル領域を調べ、すでに常駐していない領域に `os::prefetch()` を呼びます。予算判定は expert ごとの処理前に行うため、最後の expert の blob 分だけ指定容量を超える場合があります。すでに cache にある expert は読み込み数・予算の加算対象になりません。

`DS4_WARM_GB` は `warm_after()` ごとに読み直され、static cache されません。次の prompt chunk 処理を始めると既存 warm thread に停止を通知して join し、新たな先読みを始めます。モデル破棄時にも同じスレッドを停止・join します。

`--verbose` の場合、スレッド完了時に stderr へ `ds4: decode warm-up: ...` の行を出し、先読みした expert 数、候補数、読み込んだ GB、所要時間、既に RAM にあった数を表示します。条件不成立や容量 0 以下によるスキップを示す専用ログはありません。`os::prefetch()` の失敗を検査して終了・エラーにする処理はこのコード経路にはありません。

この判定に OS 分岐はありません。`os::prefetch()` の実装は Windows とそれ以外で呼び出す API を分けますが、どちらも戻り値を warm-up 側へ返さない実装です。

## 根拠

- `src/dsv41/ds4_model.cu:12779-12792` — warm-up の目的、`DS4_WARM_MIN`、GPU 数条件、既定容量、`DS4_WARM_GB` の変換と非正値の除外。
- `src/dsv41/ds4_model.cu:12793-12835` — 候補 expert の選択、重複・常駐除外、budget 判定、page-cache prefetch、verbose ログ。
- `src/dsv41/ds4_model.cu:1231,2750-2771` — `file_experts` の初期状態と GGUF、`--mmap-experts`、容量判定による設定。
- `src/dsv41/ds4_model.cu:12952-12953,13174-13184` — 次の prompt 処理で前回の warm-up を止める箇所と、prompt 処理後の `warm_after(took)` 呼び出し。
- `src/dsv41/ds4_model.cu:1895-1899` — model implementation 破棄時の warm-up 停止・join。
- `src/dsv41/ds4_os.hpp:348-367` — `os::prefetch()` の OS 分岐と戻り値を返さない実装。

候補一覧 `docs/envvars/000_envvers.md` には名前がありますが、Strata 内の実参照は上記 `src/dsv41/ds4_model.cu` の3箇所（コメント1箇所、直接読み取り2箇所）に限られます。`docs/DETAILS.md` に本変数の追加説明は見つかりませんでした。
