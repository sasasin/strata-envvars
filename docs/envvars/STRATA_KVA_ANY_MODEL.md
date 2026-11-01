# `STRATA_KVA_ANY_MODEL`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

KVA が測定済みの形状として扱うモデルは 48 層・512 experts です。`STRATA_KVA_ANY_MODEL` は、この形状条件だけを研究用途で解除し、異なる層数または expert 数のモデルでも KVA の適用判定を通します。これだけでは KVA は有効にならず、別のスイッチ `STRATA_KVA` が有効である必要があります。また、KVA のほかの適用条件はそのまま残ります。

## 値と判定

値は `kva_env_flag()` が読み、未設定または空文字なら既定値 `false` を返します。それ以外は先頭文字だけを調べ、`'0'` なら `false`、それ以外なら `true` です。文字列全体の parse、数値検証、大文字小文字変換はありません。

| 値 | `any_model` |
|---|---|
| 未設定、空文字 | `false`（既定） |
| `0`、`0anything` | `false` |
| `1`、`true`、`false`、`2`、先頭が空白の文字列など、空でなく先頭が `0` 以外 | `true` |

したがって、名前にある `ANY_MODEL=1` という表記は説明上の例で、実装は値が厳密に `1` かどうかを検査しません。境界値や無効値のエラー処理はなく、先頭文字規則で判定します。

## 有効になる条件

このフラグが影響するのは、モデルの `n_layers != 48 || n_expert != 512` のときだけです。その場合、未設定または偽なら `decline()` が「測定済み形状でない」として KVA を拒否し、真ならこの形状理由を返さず次の適用判定へ進みます。層数と expert 数の両方が基準値と異なる場合も、どちらか一方だけが異なる場合も同じ扱いです。

実際に KVA を使うには、さらに次の条件が必要です。

- `STRATA_KVA` が有効で、実行ビルドに KVA の state-only path があること。ヘッダーでは Metal を無効、それ以外（CUDA/HIP 実装）を有効としています。
- プロセス全体を止める engine 条件（複数 GPU の layer split、`--batch`、`--peer-device`）がないこと。
- 読み込みが cold read（`pos0 == 0`）、全 trunk 対象、画像なし、DFlash2 の late-layer taps なしであること。
- prompt 長が `STRATA_KVA_MIN_PROMPT` 以上かつ、完全計算 suffix に 64 を足した長さより大きいこと。

これらのいずれかを満たさない場合、この変数が真でも近似経路には入りません。CLI 引数による本変数の上書きは実装にありません。

## 実行時の詳細

`kva_config_from_env()` が `kva_env_flag("STRATA_KVA_ANY_MODEL", false)` を呼び、`kva_config()` の関数内 `static const KvaConfig` に結果を保存します。設定はプロセス内で初回 `kva_config()` 呼び出し時に一度だけ読み込まれ、その後の環境変更は反映されません。`generate.cpp` の起動時処理と prefill がこの設定を参照します。

測定外の形状で KVA が適用判定を通ると、prefill はプロセスにつき一度だけ stderr に次の警告を出します（`std::atomic<bool>` による抑制）。

```text
strata prefill: WARNING: STRATA_KVA_ANY_MODEL=1: KVA was only measured on Qwen3.8-Flash-Next (48 layers, 512 experts); this model has <層数> layers and <expert数> experts
```

`STRATA_KVA` が有効でも形状外でこの変数が偽の場合は、prefill は次の理由を stderr に出し、KVA を適用しません。

```text
strata prefill: KVA configured but NOT applied: this model's shape (<層数> layers, <expert数> experts) is not one KVA was measured on (STRATA_KVA_ANY_MODEL=1 allows it)
```

真の場合にこの変数が直接行うのは形状拒否の解除と上記警告です。KVA が適用された場合の近似処理は、split 以降の対象 layer で状態を進め、MoE を飛ばし、不要な expert transfer を計画しない処理です。適用ログと各条件による拒否ログは prefill が出します。

## 根拠

- `include/strata/prefill/kva.hpp:43-49` — Metal とその他 backend の KVA 対応判定。
- `include/strata/prefill/kva.hpp:77-84,104-133` — 設定既定値、cold read・layer split・画像・prompt 長・形状の適用条件。
- `include/strata/prefill/kva.hpp:143-146,149-163,191-195` — 値の変換、対象環境変数の読み取り、プロセス内 cache。
- `src/program/generate.cpp:6257-6279` — 起動時の設定参照と batch / GPU 分割などの process-wide 条件。
- `src/prefill/prefill.cpp:2936-2967` — 適用判定、層数・expert 数の比較、警告（プロセス中一度）。
- `src/prefill/prefill.cpp:3382-3394,3619-3629` — 適用された layer の expert transfer 抑止と state-only 処理の選択。
- `src/prefill/prefill.cpp:5820-5856` — KVA の実行ログ、未適用時の形状理由ログ。
- `docs/KVA.md:43-58,106-115` — KVA の形状条件、研究用 override と設定表。実装の値判定・適用条件は上記ソースを根拠とした。
