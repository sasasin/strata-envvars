# `STRATA_UMA_RESERVE_GIB`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-26 時点）。

## 役割

Linux の HIP ビルドで統合 GPU を使うとき、統合 GPU とシステム RAM で共有する空きメモリから、自動 expert cache 用に差し引く「OS・デスクトップ向け reserve」を GiB 単位で指定する。主なサイズ調整箇所は `strata::core::uma_desktop_reserve_bytes()` と `generate` の自動 cache sizing である。対象 GPU の空き容量と OS が報告する利用可能 RAM の小さい方を cache の予算にする処理のうち、後者から差し引く量が変わる。値自体は cache slot 数を直接指定せず、生成 token の選択や内容を制御するコードもない。`engine/include/strata/core/uma_cache.hpp:16-31` `engine/src/program/generate.cpp:9116-9135`

## 値と判定

helper は既定引数で `std::getenv` を呼び、空でない値を `std::strtod` で変換する。文字列全体の消費や `errno`、有限値、上限は検査せず、少なくとも先頭から数値を読めて `v >= 0.0` なら `v * 2^30` を `uint64_t` に変換した値を reserve とする。したがって通常の範囲では小数 GiB も受け付け、整数 byte への変換時に小数部分は切り捨てられる。先頭の空白は `strtod` が読み飛ばし、数値の後ろの文字列は無視される。`engine/include/strata/core/uma_cache.hpp:18-26`

| 条件 | unset | 設定時に有効になる値 | fallback になる値・注意 |
|---|---|---|---|
| helper が呼ばれる全経路 | `max(8 GiB, floor(total_ram / 100) * 8)`。この計算は `total_ram / 100` を先に整数除算する | `0`, `1`, `1.5`, ` 2`, `2GiB`, `0anything` など。数値 prefix が非負なら受理し、GiB を byte に換算 | 空文字、`true`、`false`、`abc`、`-1` など、数値を読めないか変換値が負なら上記既定値。`-0` は `v >= 0` なので 0 として受理。`NaN` は比較が成立せず既定値。大きさ・有限性の検査がないため、浮動小数から `uint64_t` の範囲を外れる値に有効な clamp/fallback はない |

設定値が `0` なら reserve は 0 byte になる。自動 sizing 側では reserve が 0 の場合、OS の利用可能 RAM による `free_b` の差し替え自体を行わないため、従来の GPU 空き値ベースの sizing に戻る。未設定・空文字・負値・非数値は 0 にはならず、既定 reserve を使う。`engine/include/strata/core/uma_cache.hpp:20-31` `engine/src/program/generate.cpp:9127-9135`

## 有効になる条件

- Reserve による自動 cache の予算調整は `STRATA_USE_HIP` が定義され、`_WIN32` が未定義のビルドでのみコンパイルされる。さらに `--expert-cache auto` などで `o.expert_cache < 0` の自動 sizing に入る必要がある。`generate` の cache は既定で 0（無効）なので、通常の既定設定ではこの自動 sizing は起きない。`engine/src/program/generate.cpp:895-903` `engine/src/program/generate.cpp:9077-9078` `engine/src/program/generate.cpp:9116-9127`
- その sizing 調整には、現在の HIP device の取得・property 取得が成功して `up.integrated` が真であり、`host_available_memory()` も成功する必要がある。条件を満たさない場合、この変数による OS RAM 基準の `free_b` 調整は行われない。`engine/src/program/generate.cpp:9122-9128`
- `--expert-cache N` で正の slot 数を指定すると、この変数で cache 数を変えない。対象と同じ統合 GPU・Linux HIP 条件で host RAM 情報が得られた場合には別途警告判定があり、その判定に使う headroom reserve はこの変数の値になる。`engine/src/program/generate.cpp:3984-3987` `engine/src/program/generate.cpp:9250-9266`
- `--expert-cache 0` は expert profile を読み込んだ場合に auto（`-1`）へ変換されるため、その経路では自動 sizing とこの変数が有効になる。profile がない場合の `0` は既定の cache 無効値であり、この変数は sizing を開始させない。`engine/src/program/generate.cpp:6746-6756`

## 実行時の詳細

自動 sizing では `generate.cpp` が GPU の空き byte 数を取得した後、統合 GPU かつ host memory の取得成功時に helper を呼ぶ。helper の reserve と利用可能 RAM から `max(available - reserve, 0)` を計算し、その値が GPU 空き byte 数より小さければ `free_b` をその値に差し替える。以降は `free_b` から別途 `--vram-reserve-mib` 等を引き、slot blob byte 数で割って cache slot 数を計算する。この環境変数はその先の cache size に間接的に反映される。`engine/include/strata/core/uma_cache.hpp:29-32` `engine/include/strata/core/auto_cache.hpp:30-44` `engine/src/program/generate.cpp:9127-9135` `engine/src/program/generate.cpp:9224-9249`

`getenv` の結果を保存する `static` cache はなく、helper の既定引数で呼び出しのたびに読み取る。実際の呼び出しは自動 sizing 時と、手動 cache の host memory 警告判定時である。どちらも `generate` の起動時 sizing 処理中に評価され、その後の環境変更で既に決めた slot 数や警告が再評価される処理はない。`engine/include/strata/core/uma_cache.hpp:18-23` `engine/src/program/generate.cpp:9127-9135` `engine/src/program/generate.cpp:9260-9266`

## ログと測定値

- 自動 sizing で `reserve > 0` かつ `available - reserve` が GPU 空き byte 数より小さい場合、stderr に `strata generate: expert cache auto: this GPU shares system RAM: ...` で始まる行を出す。reserve が 0 のとき、または RAM 側の値が GPU 空き値を下回らないとき、この説明行は出ない。その後、自動 cache の slot 数を `strata generate: expert cache auto: ... -> %d slots` の行に出す。`engine/src/program/generate.cpp:9127-9135` `engine/src/program/generate.cpp:9243-9249`
- 手動指定 cache が `cache_b > available - host_headroom` なら、stderr に次の警告を出す。表示文言は固定で「less 4 GiB」としているが、比較の `host_headroom` は `STRATA_UMA_RESERVE_GIB` または helper の既定 reserve であり、常に 4 GiB ではない。警告後も cache を縮めず、実際に RAM 不足となる可能性を伝える。`engine/src/program/generate.cpp:9250-9266`

  ```text
  strata generate: WARNING: this GPU shares system RAM, and the cache above (%.2f GiB) is more than the host memory available now (%.2f GiB) less 4 GiB for the OS: the system may run out of memory; --expert-cache N sets the cache by hand
  ```

Strata の `docs/STRIX_HALO.md` も自動 cache の RAM 差し引きと `--expert-cache N` の扱いを説明しているが、値の parse 規則と警告経路は上記ソースに基づく。ここでは測定値を追加しない。`docs/STRIX_HALO.md:165-169`

## 根拠

- `engine/include/strata/core/uma_cache.hpp:16-31` — 環境値の読み取り、parse、既定 reserve、RAM room の計算。
- `engine/src/program/generate.cpp:3984-3987` — `--expert-cache` の値の処理。
- `engine/src/program/generate.cpp:6746-6756` — profile 使用時の `--expert-cache 0` を auto とする処理。
- `engine/src/program/generate.cpp:9077-9139` — auto sizing の入口、HIP/Linux・統合 GPU 条件、RAM 情報取得、reserve 適用とログ。
- `engine/include/strata/core/auto_cache.hpp:30-44`、`engine/src/program/generate.cpp:9224-9249` — free byte 数から auto cache slot 数を計算・表示。
- `engine/src/program/generate.cpp:9250-9266` — 手動指定 cache でも行う host RAM 警告。
- `engine/src/core/expert_source.cpp:414-442` — Linux の host available memory の読み取り。`MemAvailable` を取得できない場合は失敗し、この helper を使う sizing 分岐に入らない。
