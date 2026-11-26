# `STRATA_KV_MAIN_OFF`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA/HIP と SYCL の QSA K/V 計画で、メインモデルの K/V ストリーミングを止め、全ページを VRAM 常駐にする A/B 用スイッチです。通常の自動または `--kv-resident` によるストリーミング条件が成立しても、この変数が設定されていればメイン層の計画を既定の全常駐状態で返します。生成ロジックや K/V の形式を直接切り替える変数ではありません。読み取りは `kv_plan` 内だけで、CUDA/HIP 側と SYCL 側に同じ判定があります（`engine/src/core/layer.cpp:738-755`; `engine/sycl/src/core/layer.cpp:722-739`）。

## 値と判定

`std::getenv(...) != nullptr` の結果だけを使います。文字列の内容は parse しません。未設定なら false、空文字列を含め何らかの値が設定されていれば true です。したがって `0`、`false`、`0anything`、空文字もすべてスイッチを有効にし、大文字小文字・空白・数値としての妥当性は判定しません（`engine/src/core/layer.cpp:744-747`; `engine/sycl/src/core/layer.cpp:728-731`）。

| 条件 | unset | 設定あり（例） | 値の内容による無効値 |
|---|---|---|---|
| CUDA/HIP または SYCL の `kv_plan` が読み取り箇所に到達 | メイン状態では通常の `--kv-resident` / 自動選択による計画を続ける | 空文字、`0`、`1`、`false`、`0anything` のいずれもメイン状態を全常駐計画にする | なし。設定有無だけを見る |
| `g_kv_resident <= 0`、または `ring_cells < 0` | 全常駐計画を返す | 環境変数を読まず、効果なし | 該当なし |

## 有効になる条件

- `g_kv_resident > 0` であること。`--kv-resident` は非負値だけを受け付け、値は `qsa_set_kv_resident` に渡されます。大きなコンテキストでは、単一 GPU・非統合メモリ・`--kv-grow` 無効などの条件下で自動的に正の resident window が選ばれる経路もあります（`engine/src/program/generate.cpp:5028-5032`; `engine/src/program/generate.cpp:4234-4277`）。
- `ring_cells >= 0` であること。通常のメインセッションは既定の `ring_cells=0` で計画されます。`ring_cells > 0` のリング状態では条件式が `STRATA_KV_RING_OFF` を選ぶため、この変数はリング状態を切り替えません。`ring_cells < 0` は環境変数判定より前に全常駐で返ります（`engine/include/strata/core/layer.hpp:287`; `engine/src/core/layer.cpp:743-750`）。
- ストリーミング可能な範囲であること。スイッチ未設定時も、ページ丸め後の resident slot 数 `r` が全ページ数 `p.pages` 未満にならなければ `kv_mode=1` にはならず、変数による計画差はありません。設定時はこの比較より前に全常駐計画を返します（`engine/src/core/layer.cpp:738-755`）。
- 読み取り箇所は CUDA/HIP 用と SYCL 用の `layer.cpp` にあります。リポジトリ全体の参照検索では Metal 実装その他に読み取りはありません。OS 固有やモデル形式固有の追加判定はこの変数の読み取りにはありません。

## 実行時の詳細

`kv_plan` はまずコンテキスト全体のページ数・slot 数を設定します。`g_kv_resident <= 0` または負の `ring_cells` ならそのまま返り、それ以外で初めて関数内 `static` の `main_off` が初期化されます。したがって値はプロセス内で最初にこの初期化へ到達した時点で固定され、実行中に環境を変更しても反映されません。最初の呼び出しが早期 return した場合は、後の適格な呼び出しで初期化されます（`engine/src/core/layer.cpp:738-747`; `engine/sycl/src/core/layer.cpp:722-731`）。

スイッチが設定されている場合、`KvPlan` の初期値（`mode=0`、全ページ分の `slots`）を返します。`qsa_state_bytes` と `qsa_state_init` は同じ計画を使い、mode 0 では K/V pool を全 slot 分確保し、ページテーブルを identity にします。ストリーミング時の pinned RAM コピーと residency map は作られず、attention 呼び出しの `qsa_kv_resolve` も mode 1 以外では何もしません（`engine/src/core/layer.cpp:788-805`; `engine/src/core/layer.cpp:807-825`; `engine/src/core/layer.cpp:879-893`; `engine/src/core/layer.cpp:925-960`; `engine/src/core/layer.cpp:975-980`; `engine/src/core/layer.cpp:1031-1035`）。

通常の CLI `generate` 経路では、この設定は `--kv-resident` や自動選択より後に計画へ適用される veto です。CLI 値や別の環境変数でスイッチを解除する処理は見つかりません。ストリーミングを抑止すると必要な K/V VRAM 量は全ページ分になりますが、生成 token や選択結果が同一になるかはこの分岐だけからは確認できません。

## ログと測定値

この変数専用のログはありません。計画が mode 1 のときは `strata generate: KV streaming: %lld of %lld cells per QSA layer in VRAM, the K/V in %.2f GiB of pinned RAM` が出ます。変数が全常駐計画にした場合、このストリーミング有効ログは出ません（`engine/src/program/generate.cpp:7742-7746`）。

ストリーミング計画で pinned RAM の確保または device pointer 取得に失敗すると、mode 1 では `strata: KV streaming: cannot pin ...` の警告を出し、state 初期化が失敗します。呼び出し元は `session_init failed` で `generate` を終了します。全常駐にした経路でも、必要な VRAM を確保できなければ `session state allocation failed` または `session_init failed` となり得ます（`engine/src/core/layer.cpp:925-938`; `engine/src/core/session.cpp:108-114`; `engine/src/program/generate.cpp:7734-7740`）。この変数の効果を比較した測定値は、参照した実装と `docs/DETAILS.md` に記載されていません。

## 根拠

- 全参照と読み取り箇所: `engine/src/core/layer.cpp:744-747`; `engine/sycl/src/core/layer.cpp:728-731`。
- mode 0/1/2 の意味: `engine/include/strata/core/layer.hpp:234-238`。
- CLI の resident 値設定と自動選択条件: `engine/src/program/generate.cpp:5028-5032`; `engine/src/program/generate.cpp:4234-4277`。
- 計画に基づく state 確保、失敗経路、ストリーミングログ: `engine/src/core/layer.cpp:788-805`; `engine/src/core/layer.cpp:807-825`; `engine/src/core/layer.cpp:925-938`; `engine/src/core/session.cpp:108-114`; `engine/src/program/generate.cpp:7734-7746`。
