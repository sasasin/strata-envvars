# `STRATA_PREFILL_LM_R`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

layer-major prefill が使う super-chunk の残差行列 `R` の置き場所を選びます。`vram` は super-chunk 全体の残差行列を GPU メモリに置き、`host` は pinned host RAM に置いて sub-chunk ごとに GPU との間で転送します。未設定または認識されない値は自動選択です。

この変数だけでは layer-major prefill は有効になりません。layer-major が別の設定・実行条件で選ばれ、`lm_prepare()` まで到達したときにだけ参照されます。

## 値と判定

`lm_r_env()` は最初の評価時に `std::getenv()` の結果を文字列全体で比較し、その整数結果を関数内の `static const` に保存します。

| 環境変数の値 | 判定 | 選択 |
|---|---:|---|
| 未設定 | 0 | 自動 |
| `vram`（小文字・完全一致） | 1 | VRAM を指定 |
| `host`（小文字・完全一致） | 2 | pinned host RAM を指定 |
| 空文字、`VRAM`、`host `、数値、その他の文字列 | 0 | 自動 |

前後の空白除去、大文字小文字変換、数値変換はありません。無効値を警告する処理もありません。プロセス内で最初に `lm_r_env()` が評価された後の環境変更は反映されません。

## 有効になる条件

- 通常の `Prefill::run()` が layer-major を選択し、準備処理まで成功する必要があります。`STRATA_PREFILL_LAYER_MAJOR`、CUDA/HIP の別、stage 数、`STRATA_DEFAULTS=026` による有効化規則が先に適用されます。未設定時の既定有効条件は CUDA の layer split（2 stage 以上）で、単一 GPU、HIP、`STRATA_DEFAULTS=026` では既定 OFF です。明示的な layer-major 要求があっても、HIP は実行時に `STRATA_LM_HIP=1` がなければ準備を拒否します。
- 画像 prompt、peer GPU、特定の layer split hand-off、DFlash2 prompt taps、`STRATA_KVA`、chunk 境界で yield する batch read、`--prefill-pipe` の計画などでは layer-major の準備が拒否されます。`STRATA_EXPERT_NIBBLE` や debug dump、モデル／expert plan と必要バッファの条件も判定されます。
- `STRATA_PREFILL_LM_TOKENS`、利用可能な VRAM、および `STRATA_PREFILL_LM_MARGIN_MIB` が決める空き領域の余裕が、super-chunk のサイズと収容可否に影響します。後段の layer-split stage はこの環境変数によらず host mode に固定されます。

## 実行時の詳細

先頭 stage では、`vram` 指定時に VRAM 上で収まる最大の super-chunk を探し、`host` 指定時には pinned RAM に残差行列を置く方式で最大サイズを探します。明示指定でも要求サイズ全部が収まる必要はなく、`fit()` は chunk 単位でサイズを下げます。自動時は、目標 super-chunk 全体が VRAM に収まる場合だけ VRAM を選び、それ以外は host mode を試します。自動時の host mode で探すサイズが 0 なら準備失敗です。

host mode では層の計算後に残差行列を device-to-host copy し、次の層の計算前に host-to-device copy します。VRAM mode では残差行列を保持し、sub-chunk ごとの残差転送はしません。どちらも layer-major の他の処理条件が変わるものではありません。

強制した配置が収まらない、pinned RAM の確保に失敗する、または device buffer の確保に失敗する場合、`lm_prepare()` は理由を返します。通常の `Prefill::run()` はその prompt について layer-major を使わず `run_impl()` の通常経路へ進み、理由ごとに `strata prefill: layer-major off for this prompt: ...` を stderr に出します（既定で layer-major の短い prompt による辞退はログ抑制）。layer-major が実行された場合の stderr ログ `strata prefill: layer-major ... (R in VRAM|pinned RAM, ...)` で実際の配置を確認できます。実行中の残差ダウンロード失敗は `prefill (layer-major): the residual rows' download failed` となり、処理失敗として返されます。

`run_multi()` も `lm_prepare_chain()` を呼びますが、準備失敗時は `prefill: multi-prompt read declined: ...` をエラーとして返し、単一 prompt の `run()` と同じ通常経路への fallback にはなりません。

## 根拠

- 候補名の実読み取りと判定、static cache: `src/prefill/prefill.cpp:5914-5922`。全参照検索では、候補名の文字列を含む箇所はこの読み取りと説明コメントの `src/prefill/prefill.cpp:5888-5889` のみです。
- 選択方法、VRAM 収容判定、失敗理由、後段 stage の host 固定: `src/prefill/prefill.cpp:6034-6061`。
- pinned RAM 確保と GPU buffer 確保の失敗: `src/prefill/prefill.cpp:6075-6088`。
- host mode の残差行列転送と失敗: `src/prefill/prefill.cpp:6696-6704,6722-6729,7113-7122`。
- layer-major の有効条件、実行、通常経路への fallback とログ: `src/prefill/prefill.cpp:5955-5995,7222-7271`。HIP の追加 opt-in は `src/prefill/prefill.cpp:5958-5967`。
- 未設定時の layer-major 既定値と `STRATA_PREFILL_LAYER_MAJOR` の解決: `include/strata/core/sm120_series.hpp:107-119`。
- 複数 prompt 経路の準備失敗: `src/prefill/prefill.cpp:6188-6197`。
