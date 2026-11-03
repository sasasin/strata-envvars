# `STRATA_MTP_KEEP`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。外部ライブラリの環境変数は対象外。

## 役割

単一 GPU の起動時に、空き VRAM が MTP draft 層などの見積もり必要量を下回った場合でも、`--mtp` で指定した draft 層を自動で外さずロードを試みます。変数が未設定なら、条件に応じて Strata は `--mtp` をクリアして draft 層なしで起動します。

## 値と判定

値の内容は読みません。`std::getenv("STRATA_MTP_KEEP") == nullptr` だけを判定するため、**変数が存在すれば値が空文字、`0`、`false`、その他の文字列でも**自動除外を抑止します。従って説明ログの `STRATA_MTP_KEEP=1` は設定例であり、`1` だけを有効値として parse する実装ではありません。

| 状態 | 低 VRAM 時の処理 |
|---|---|
| 未設定 | 他の適用条件も満たせば必要量を見積もり、不足時に MTP 層を外す |
| 設定あり（空文字を含む） | この自動除外ブロックを通らず、後続の MTP ロードを試す |

根拠: `src/program/generate.cpp:6721-6740`。

## 有効になる条件

自動除外（この変数を unset にしたときの既定動作）は、次のすべてを満たす場合だけ評価されます。

- `--mtp` が空でない。
- DFlash2 単独ロードの経路ではない（`use_df2` が false）。
- `multi_gpu` が false で、staged 経路も空（`stages.empty()`）。
- `STRATA_MTP_KEEP` が未設定。
- `spill_discrete_gpu()` が true。

Metal ビルドでは `spill_discrete_gpu()` は false を返します。その他のビルドでは CUDA device / properties の取得が成功し、`integrated` でない GPU の場合にだけ true です。したがって Metal、統合 GPU、device 情報取得失敗時は、この変数の有無によらず当該自動除外判定は行われません。根拠: `src/program/generate.cpp:271-284`, `include/strata/core/spill_gate.hpp:8-14`。

この判定の後、`--spec` が 2 未満なら `--mtp` 自体が無視されます。保持指定は `--spec` の条件を上書きしません。根拠: `src/program/generate.cpp:6742-6747`。

## 実行時の詳細

判定は `generate` の起動処理中、MTP load より前に一度実行されます。環境値は static cache されません。判定ブロックでは `--mtp` の `dense.bin` と `experts.bin` のサイズを足し、必要時には native output head のサイズも見積もります。必要量は `layer_b + head_b + 220 MiB + 1550 MiB` で、空き量が正かつ必要量未満なら stderr に `short of GPU memory: ... this start runs without the draft layer (decode is slower; STRATA_MTP_KEEP=1 keeps it` と出し、`o.mtp.clear()` します。ファイルサイズ取得に失敗した場合や空き量が 0 の場合は、この不足判定に入りません。根拠: `src/program/generate.cpp:6726-6740`。

`o.mtp` が残れば `mtp.load(...)` が実行され、失敗時はエラーと VRAM の補足を stderr に出して終了コード 1 を返します。したがって変数設定はロード成功を保証せず、メモリ不足などによるロード失敗を無視する指定でもありません。根拠: `src/program/generate.cpp:6761-6764`; `src/core/mtp.cpp:302-323,329-340`。

自動除外された場合は、Strata の `docs/DETAILS.md` が説明する suffix / prompt-lookup drafter による draft 経路が残り、token は引き続き検証されます（`docs/DETAILS.md:338`）。これは Strata 文書の説明であり、この調査では生成結果や速度を実行測定していません。

## 根拠

- 候補一覧への掲載: `docs/envvars/000_envvers.md:1506`。
- 唯一の実装参照（判定、見積もり、警告、`o.mtp.clear()`）: `src/program/generate.cpp:6721-6740`。
- GPU 種別によるゲート: `src/program/generate.cpp:271-284`, `include/strata/core/spill_gate.hpp:8-14`。
- 後続の MTP load と失敗時終了: `src/program/generate.cpp:6742-6764`, `src/core/mtp.cpp:302-323,329-340`。
- MTP 層を使わない場合の draft 経路の説明: `docs/DETAILS.md:334-340`。
