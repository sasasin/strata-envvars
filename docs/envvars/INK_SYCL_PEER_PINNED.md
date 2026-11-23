# `INK_SYCL_PEER_PINNED`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

SYCL Inkling の dual-GPU Expert Parallelism (EP) 初期化時に、GPU 間の peer access 試験を省略して `ep2_p2p` を false にし、pinned-host bounce 経路を選ばせます。モデルの GPU 割り当てや EP split の値はこの変数では変更しません。読み取りは `ink_sycl::probe_p2p` です（`engine/src/inkling2/sycl/ink_sy_common.h:132-135`）。

## 値と判定

`std::getenv` で設定有無を得て、値の先頭 1 文字だけを `=='1'` で比較します。文字列全体の parse、空白除去、大文字小文字変換、数値妥当性検査はありません。

| 条件 | unset | 有効になる値（P2P を強制的に無効化） | 無効になる値（通常の P2P 試験へ進む） |
|---|---|---|---|
| SYCL Inkling dual-GPU `.strata` 読み込みで P2P probe に到達 | 環境値による強制なし | 先頭文字が `1` の値。例: `1`、`10`、`1anything` | 空文字、`0`、`true`、`false`、`01`、` 1`、`2` |

未設定では `getenv` が null となり、空文字では先頭文字が `\0` のためどちらも早期 return しません。設定値の先頭文字が `1` なら `probe_p2p` は直ちに false を返し、SYCL peer-access API や転送試験を呼びません（`engine/src/inkling2/sycl/ink_sy_common.h:132-171`）。

## 有効になる条件

- SYCL Inkling バックエンドのビルド・実行経路であること。SYCL プラグインは `strata_inkling_sycl` として定義され、`strata-inkling` にリンクされます（`engine/src/inkling2/sycl/CMakeLists.txt:7-8,43-45`）。
- `ModelSourceKind::Strata` の初期化であること。統合バックエンドはこの場合に `mod_.load(...)` を呼び、別のモデル形式では `load_from_model_file(...)` を呼びます（`engine/src/inkling2/sycl/ink_sycl_backend.cpp:94-99`）。環境変数の読み取り箇所は `.strata` 用 `load` の P2P probe だけです。
- `--gpus` / `--devices` 等で 2 GPU 以上を要求し、SYCL GPU が 2 台以上見えて、GPU 1 の VRAM budget が正であること。条件を満たすと `load` が probe を呼んで `ep2_active` にします（`engine/src/inkling2/sycl/ink_sy_common.h:784-834`）。standalone CLI は `--gpus` / `--devices` を読み、最終的に `mod.load(...)` を呼びます（`engine/src/inkling2/sycl/ink_sy_main.cpp:129-145,183`）。
- 1 GPU 実行、GPU 1 の予算がゼロ、または他形式のモデル読み込みではこの変数による probe はありません。SYCL peer-access 拡張 macro がない build、peer access 不可、probe 中の例外でも probe は false を返すため、変数が unset でも pinned-host 経路になります（`engine/src/inkling2/sycl/ink_sy_common.h:135-171`）。

## 実行時の詳細

環境値は `probe_p2p` の呼び出し時に読むだけで、static cache にはしません。dual-GPU `.strata` load 中の probe は GPU 1 budget が正の場合に 1 回呼ばれ、その結果はモデルの `ep2_p2p` フィールドに保存されます。以後の生成処理は環境値を再読せずこのフィールドで分岐するため、probe 後にプロセス環境を変えても現在のモデル状態には反映されません（`engine/src/inkling2/sycl/ink_sy_common.h:132-135,817-823`）。

値の先頭が `1` なら P2P probe をせず `ep2_p2p=false` となります。dual-GPU EP 自体が有効な場合、GPU 0 から pinned host scratch へデータをコピーして同期した後、GPU 1 へ送ります。GPU 1 の出力も pinned host scratch に戻し、GPU 0 へ転送して GPU 0 の部分和と加算します。通常の P2P 成功時は GPU 間の直接コピーを使います（`engine/src/inkling2/sycl/ink_sy_runner.h:623-675`）。これは通信経路の選択で、expert 配分は同じ `ep2_active` / split の条件で行われます（`engine/src/inkling2/sycl/ink_sy_common.h:837-885`）。

## ログと測定値

環境変数の値そのものや強制切替の専用警告は出力しません。dual-GPU load が成功すると `[ink_sycl] loaded ... | Dual-GPU EP2 ... %s ...` の `%s` に `p2p` または `pinned` が出ます（`engine/src/inkling2/sycl/ink_sy_common.h:971-980`）。統合バックエンドの device info も `[EP-2GPU split=..., p2p]` または `[EP-2GPU split=..., pinned]` を含めます（`engine/src/inkling2/sycl/ink_sycl_backend.cpp:39-49`）。`pinned` 表示だけでは本変数による切替か、peer access 不可・未対応など別理由かは区別できません。資料に本変数の条件付き測定値は確認できません。

## 根拠

- `engine/src/inkling2/sycl/ink_sy_common.h:132-171` — 環境値判定、SYCL peer access probe、および false の各経路。
- `engine/src/inkling2/sycl/ink_sy_common.h:784-834` — dual-GPU 条件、probe 呼び出しと初期化 fallback。
- `engine/src/inkling2/sycl/ink_sy_common.h:837-885,971-980` — GPU expert 配置と load ログ。
- `engine/src/inkling2/sycl/ink_sy_runner.h:623-675` — 保存された P2P 判定に応じた生成時の転送経路。
- `engine/src/inkling2/sycl/ink_sycl_backend.cpp:39-49,94-99` — device info 表示と統合バックエンドのモデル形式分岐。
- `engine/src/inkling2/sycl/ink_sy_main.cpp:129-145,183`、`engine/src/inkling2/sycl/CMakeLists.txt:7-8,43-45` — standalone の起動経路と SYCL プラグイン build。
