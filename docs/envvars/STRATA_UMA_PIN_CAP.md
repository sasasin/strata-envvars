# `STRATA_UMA_PIN_CAP`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

Windows HIP ビルドで、複数スロットの起動時に RAM 常駐 expert copy の予算を制限する。K/V streaming の各セッションが pin する RAM と expert copy の合計を基準値以下にし、予算からあふれた expert は RAM copy に置かず、モデルファイルから読む。GPU cache、スロット数、context 長、prompt chunk はこの制限では変更しない（`src/program/generate.cpp:11220-11229`）。

## 値と判定

値を数値や真偽値として parse せず、環境変数の先頭文字が `'0'` かだけを見る。先頭文字が `'0'` なら cap 判定を丸ごとスキップし、既存の RAM budget を維持する。未設定、空文字、先頭が `'0'` 以外の文字列では cap を有効にする（`src/program/generate.cpp:11230-11240`）。

| ビルド | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `STRATA_USE_HIP` と `_WIN32` の両方が定義されたビルド | 条件成立時に cap を判定 | 空文字、`1`、`true`、`false`、` 0`、`-1` など、先頭が `0` 以外 | `0`、`0anything`、`00`、`0.0` など、先頭が `0` |
| その他のビルド | 対象箇所がコンパイルされず、効果なし | 効果なし | 効果なし |

値全体の妥当性、大文字小文字、空白、数値としての意味は検査しない。先頭の空白は読み飛ばされない。空文字は「設定あり」でも先頭文字が `'0'` ではないため cap を有効にする。

cap は `22.75 GiB - qsa_kv_host_bytes()` で計算し、差が 0 以下なら cap は 0 bytes になる。RAM budget API では 0 が「無制限」を意味するため、その場合に限り実際に渡す予算は 1 byte とし、expert copy に blob が入らないようにする（`include/strata/core/uma_cache.hpp:45-62`）。もとの `o.resident_budget` がこの予算以下なら変更しない。大きい場合だけ上限まで下げる（`src/program/generate.cpp:11233-11240`）。

## 有効になる条件

- Windows HIP のビルドであること。cap の読み取りと適用は `#if defined(STRATA_USE_HIP) && defined(_WIN32)` の内側にある（`src/program/generate.cpp:11220-11242`）。
- 実行時に `--batch` / `--slots` が 2 以上で有効なこと。batch は `--serve` が必要で、serve 以外や 2 未満では警告後に batch が 0 に戻される（`src/program/generate.cpp:3857-3858, 7475-7481`）。
- Strix Halo 相当の gfx1151、全可視 GPU が同じ gfx1151 統合 GPU、Windows の経路で `o.prefill_own_keep_chunk` が有効であること。この値は `STRATA_PREFILL_BORROW=1` でなく、かつ `STRATA_GFX1151_DEFAULTS` が先頭 `'0'` でない場合に設定される（`src/program/generate.cpp:4080-4090, 4186-4192`）。
- mmap-backed resident RAM mode が構築され、`o.resident_budget > 0` であること。正の予算は `--resident-budget-gib N` から来るか、expert arena の RAM 不足時に profile があり `STRATA_ARENA_FALLBACK_RESIDENT=0` で無効化されていない自動 resident fallback から来る（`src/program/generate.cpp:4036-4044, 8045-8048, 8313-8329`）。予算 0 の `--resident-experts` / `--resident-cpu-experts` にはこの cap は適用されない。
- `STRATA_UMA_PIN_CAP` の先頭が `'0'` でないこと。`STRATA_RESIDENT_PIN` など RAM copy の pin 方法を選ぶ設定は別判定であり、この cap 値の parse や予算計算には使われない（`src/program/generate.cpp:11232-11240`）。

## 実行時の詳細

resident copy の構築中、K/V host bytes を取得して cap を計算し、必要なら `o.resident_budget` を小さくしてから `FileExpertSource::pin_cache_complement` に渡す。呼び出しは profile 順に GPU cache が保持しない expert を選び、予算に収まらないものはファイル側に残す（`src/program/generate.cpp:11230-11246`; `src/core/expert_source.cpp:3633-3676`）。K/V host bytes は QSA の K/V host allocation 成功時に加算され、`qsa_kv_host_bytes()` がその合計を返す（`src/core/layer.cpp:917-933`; `src/core/layer.cpp:786`）。

環境変数はこの resident copy 構築時に `std::getenv` で読み、static cache には保存しない。通常の generate/serve 起動では起動時の resident copy 形成に使われ、実行中の環境変更を再評価する要求単位の読み取りではない（`src/program/generate.cpp:11230-11246`）。CLI の正の `--resident-budget-gib` は初期予算を指定し、この環境変数はその値を超えないよう縮めるか、先頭 `'0'` で縮小を止める。CLI が指定した budget 自体を無視して別の値に置き換えるものではない（`src/program/generate.cpp:4036-4044, 11233-11240`）。

soft resident mode で cap 適用後の最初の構築が失敗すると、再試行は `kResidentWhatFits` 予算で行われる。この再試行には先ほどの cap 予算を渡さないため、再試行時の保持量は cap に制限されない（`src/program/generate.cpp:11257-11264`）。最初の構築も再試行も失敗し、soft mode でもない場合は、正の RAM budget を保持できない旨を警告して expert を model files から読む経路へ進む。resident budget が 0 の別経路では `CPU expert residency` エラーを出して終了する（`src/program/generate.cpp:11339-11353`）。

## ログと測定値

予算が実際に縮められ、resident copy が成功して設定 cap 近くまで保持した場合、stderr に次のいずれかを出す（`src/program/generate.cpp:11247-11255`）。

- cap が 0 の場合: `strata: %d requests at once: the experts are read from the SSD when needed so that everything fits in this PC's memory (STRATA_UMA_PIN_CAP=0 keeps the RAM budget as set)`
- cap が正の場合: `strata: %d requests at once: %.1f GiB of experts are kept in RAM so that everything fits in this PC's memory; the rest are read from the SSD when needed (STRATA_UMA_PIN_CAP=0 keeps the RAM budget as set)`

この専用ログは、cap がもとの予算より小さくならなかった場合や resident 構築が失敗した場合には出ない。成功時には別途 `FileExpertSource: RAM budget ...`、`FileExpertSource: ... cache complement ready: resident ...`、`strata generate: resident RAM mode: ...` などの通常ログがあり、構築失敗は上記の warning / error 経路で観測できる（`src/core/expert_source.cpp:3674-3676, 4243-4247`; `src/program/generate.cpp:11332-11353`）。

cap の 22.75 GiB 基準はソースコメント上の Windows HIP / Strix Halo の試行に基づく。UD-Q4_K_XL、131,072 context、4 slots で expert complement 15 GiB + pinned K/V 7.75 GiB の合計 22.75 GiB は開始し、18 GiB + 7.75 GiB は失敗した記録であり、一般的な上限の測定値ではない（`include/strata/core/uma_cache.hpp:45-54`）。

## 根拠

- 直接の環境変数読み取り、guard、cap 適用と専用ログ: `src/program/generate.cpp:11220-11255`
- cap 値と 0-byte budget の扱い: `include/strata/core/uma_cache.hpp:45-62`
- バッチの serve 条件: `src/program/generate.cpp:7475-7489`
- gfx1151 Windows HIP の own-buffer 条件: `src/program/generate.cpp:4080-4090, 4186-4192`
- resident budget と fallback 起点: `src/program/generate.cpp:4036-4044, 8045-8048, 8313-8329`
- profile 順の budget 選択、resident 成功ログ: `src/core/expert_source.cpp:3633-3676, 4243-4247`
