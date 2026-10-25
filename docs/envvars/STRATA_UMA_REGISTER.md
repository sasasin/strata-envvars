# `STRATA_UMA_REGISTER`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。作業開始時の作業ツリーは clean。外部ライブラリの環境変数は対象外。

## 役割

統合 GPU の一部でエンジンが選ぶ UMA mode（expert arena を GPU driver に登録しない動作）を解除し、従来どおり登録するための opt-out です。主な現行経路は HIP build の Windows 上で Strix Halo（`gfx1151`）を使う場合です。Linux の Radeon 780M（`gfx1103`）向けにも同じ判定関数がありますが、現在の起動側は既定の `on=false` を渡すため、その経路ではこの変数を設定しない限り登録なしの mode にはなりません。

## 値と判定

| 環境変数 | `igpu_uma_arena_default()` の判定 |
|---|---|
| 未設定 | architecture/platform の既定判定を続ける |
| 空文字 | 未設定と同じ。先頭文字は `\0` なので opt-out にならない |
| 先頭文字が `1` | false を返し、エンジンによる UMA mode 選択を抑止する。`1`, `10`, `1abc` など |
| その他の設定値 | architecture/platform の既定判定を続ける。`0`, `true`, 空白始まり、`none` など |

数値変換や文字列全体の比較はありません。大文字小文字も関係せず、先頭文字だけが判定されます。値が `1` でも `STRATA_ARENA_PIN_GIB=none` が指定されると、arena 側の明示指定が優先され、登録なしになります。

## 有効になる条件

- Strata の HIP build で `generate` の起動経路を通ること。環境判定と UMA flag の設定は `STRATA_USE_HIP` のコンパイル条件内です。CUDA-only、Metal、SYCL build にはこの処理がありません。
- GPU 情報の取得後、見えている全 GPU が統合 GPU で同じ architecture であること。複数 GPU が混在する場合、起動側は `integrated=false` として渡します。
- 変数の先頭文字が `1` でないこと。
- Linux の `gfx1103` ではさらに `on=true` が必要ですが、現行起動コードは省略時既定値 `false` を渡します。したがって現行の既定起動では、この変数だけで Linux `gfx1103` を UMA mode に切り替えることはありません。
- Windows では `gfx1151` の統合 GPU が対象です。`on` 引数とは独立して既定で登録なしになります。Windows の他 architecture、Linux の `gfx1151` はこの分岐では対象外です。
- `STRATA_ARENA_PIN_GIB` が空または未設定なら、上記の起動時 flag が arena に適用されます。値が `none` なら登録なしを明示し、その他の非空値（`0` を含む）は起動時 flag を上書きして登録経路を選びます。
- Windows の `STRATA_DEFERRED_REGISTER=1` が有効で、arena が by-need でも共有 arena でもなく、engine pin cap がなく、`STRATA_ARENA_PIN_GIB` の解析結果が `-1` のときは、登録なし flag を迂回する deferred constructor が選ばれます（`STRATA_ARENA_PIN_GIB=none` も解析結果は `-1`）。この経路では `STRATA_UMA_REGISTER` の判定結果にかかわらず layer ごとの登録が試みられます。

## 実行時の詳細

HIP `generate` は起動時に GPU 0 の properties と device count を調べ、全 device が統合 GPU かつ同一 architecture かを確認します。その結果を使って `igpu_uma_arena_default()` を呼び、true の場合だけ `arena_uma_no_register_flag` を立てます。この環境変数自体はこの初期化時に読み取られ、リクエストごとには再評価されません。

通常の expert arena 確保時、`arena_no_register()` はまず `STRATA_ARENA_PIN_GIB` を読みます。空でない場合、完全一致する `none` のみが登録なしを指定し、それ以外は登録なし flag を無視します。登録なし経路では CUDA host registration を行わず、通常ページなら `STRATA_ARENA_LOCK` が未設定または文字列全体が `0` 以外のとき working-set lock を試みます。Windows では working-set minimum を arena サイズと余裕分だけ増やしてから `VirtualLock` を最大 1 GiB ずつ呼びます。大ページの場合は追加 lock を行いません。ロック失敗で登録を試し直す処理はなく、arena の note にロック結果が残ります。

ただし Windows の `STRATA_DEFERRED_REGISTER=1` が上記条件を満たして選ばれると、別 constructor が arena を予約し、後から各 layer の slice を直接登録します。この constructor は `arena_no_register()` / `STRATA_UMA_REGISTER` を確認しません。したがってこの経路では `STRATA_UMA_REGISTER` で要求した登録なし動作は実現せず、`STRATA_ARENA_PIN_GIB=none` も deferred 選択を防ぎません。

この経路では `registered_bytes` が 0 となり、expert arena の通常の driver 登録や登録範囲を使った PCIe share はありません。stderr の `strata generate: expert arena: ...` に `NOT registered with the GPU driver (integrated GPU, UMA mode; STRATA_ARENA_PIN_GIB=0 registers it)` と resident lock の結果が表示されます。`STRATA_ARENA_PIN_GIB=0` などで通常の登録経路に戻した場合は、arena の通常 registration / fallback 規則が使われます。

## 根拠

- `src/core/arch_defaults.cpp:76-86` — 先頭文字 `1` の判定、Windows `gfx1151` と Linux `gfx1103` の選択条件。
- `src/program/generate.cpp:2769-2797` — HIP build 限定の呼び出し、全 GPU の integrated / architecture 条件、flag 設定位置。
- `include/strata/core/arch_defaults.hpp:35-41,50-54` — 780M では既定 off、Windows Strix Halo の例外、起動時に環境既定値を適用する設計。
- `src/core/pinned.cu:346-359,418-435` — `STRATA_ARENA_PIN_GIB` の優先順位と登録なし経路。
- `src/core/expert_source.cpp:5854-5871`, `src/core/pinned.cu:615-655` — Windows deferred registration の選択条件と、UMA flag を参照しない layer 登録。
- `src/platform/memory.cpp:22-60` — Windows working-set 設定と `VirtualLock` の実装。
- `src/program/generate.cpp:5830-5834` — expert arena note の stderr 出力。
- `docs/STRIX_HALO.md:11` — Windows Strix Halo での既定動作と `STRATA_UMA_REGISTER=1` / `STRATA_ARENA_PIN_GIB` による登録の説明。これは文書の記述であり、調査時に Windows 実機で再測定したものではありません。
