# `STRATA_KV_RESIDENT_MIN`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

KV streaming を使うとき、通常の QSA 層ごとに VRAM 上へ残す KV window の下限（cell 数）を指定します。`--kv-resident N` で要求した数がこの下限より小さい場合に下限まで引き上げ、残りの KV を pinned RAM に置く計画にします。変数単独では streaming を有効にしません。

## 値と判定

`std::atoll` で値の先頭から整数を読みます。変換結果が `1024` 以上ならその値を下限として使います。未設定、空文字、数値に変換できない文字列、`1024` 未満（負値を含む）は、ビルドに応じた既定値に戻ります。`atoll` は整数の後ろの非数値部分を検査しないため、たとえば `2048tail` は `2048` として扱われます。値全体の妥当性検査や clamp はありません。

| 実装 | 既定値 | `atoll` の結果が 1024 以上の場合 |
|---|---:|---|
| `src/core/layer.cpp` の Metal build | 20480 cells | 指定値 |
| `src/core/layer.cpp` の Metal 以外の build（CUDA/HIP 系） | 4096 cells | 指定値 |
| SYCL (`sycl/src/core/layer.cpp`) | 20480 cells | この変数を読まず、常に 20480 cells |

## 有効になる条件

- `--kv-resident` が正であること。未指定時の既定値は `0` で、`qsa_set_kv_resident` は 0 以下を 0 にするため、KV は全体が VRAM resident のままです。
- メイン QSA 層の KV が context 全体より小さくなること。実装は `max(--kv-resident, qsa_kv_resident_min())` を page 単位に切り上げ、必要 slot 数が context の page 数より少ない場合にだけ streaming mode にします。下限が context 以上なら全体 resident となり、変数の効果は現れません。
- `STRATA_KV_MAIN_OFF` が設定されていないこと。設定有無だけでメイン層の streaming を止めます（空文字も設定扱い）。`STRATA_KV_RING_OFF` は drafter の ring 用で、ring はこの下限でなく ring の長さから slot 数を決めます。

`--kv-resident` は非負である必要があり、負値では stderr に `strata generate: --kv-resident must be >= 0` を出して終了コード 2 で終了します。CLI 値は `atoll` で読まれ、環境変数は CLI 値を置き換えず、正の CLI 値に対する下限として `max` で適用されます。したがって `--kv-resident 0` は環境変数が設定されていても streaming を無効のままにします。

## 実行時の詳細

環境値の読み取り箇所は `src/core/layer.cpp` の `qsa_kv_resident_min()` だけです。関数内の function-local `static` に変換結果を保存し、最初の呼び出し時に一度評価します。通常は session の QSA state サイズ計算・初期化中に `kv_plan()` から呼ばれるため、その後にプロセス環境を変更しても値は更新されません。別の共通 env helper や動的な名前渡しによる読み取りはありません。

通常の QSA 層は、計画された slot 数分の KV pool を VRAM に置き、全 context 分の KV copy を pinned RAM に確保します。pinned RAM の確保に失敗すると `src/core/layer.cpp` が `strata: KV streaming: cannot pin ...` を stderr に出し、state 初期化が失敗します。generate 経路ではその後 `strata generate: session_init failed` を出して終了コード 1 になります。成功時に streaming mode なら、generate は `strata generate: KV streaming: ...` の行で VRAM 上の cells、context 長、pinned RAM 量を stderr に報告します。

環境変数が受理された値でも、`--kv-resident` が 0、context が下限以下、または `STRATA_KV_MAIN_OFF` が設定されていると通常層の streaming は起きません。drafter ring は `ring_cells > 0` の別分岐で計画され、resident floor の適用対象外です。SYCL の実装は同名変数を参照せず、下限を固定値 20480 にします。

## 根拠

- `src/core/layer.cpp:771-785` — 環境変数の単一読み取り、`atoll`、Metal / その他の既定値、static cache。
- `src/core/layer.cpp:738-755` — `--kv-resident` の値と floor の比較、page 単位の切り上げ、context 全体なら streaming しない条件、ring 分岐。
- `src/core/layer.cpp:769-770` — 0 以下の CLI 値を 0 にする setter。
- `src/core/layer.cpp:917-933` — streaming 時の pinned RAM copy 確保と失敗ログ。
- `src/program/generate.cpp:3357-3359,4128-4132` — `--kv-resident` の CLI 変換、負値エラー、値の設定。
- `src/program/generate.cpp:6376-6388` — session 初期化失敗時の終了、streaming 成功ログ。
- `src/core/session.cpp:108-115` — QSA state 初期化失敗を session 初期化失敗として返す。
- `sycl/src/core/layer.cpp:722-739,753-756` — SYCL の KV 計画と固定 20480 floor。
