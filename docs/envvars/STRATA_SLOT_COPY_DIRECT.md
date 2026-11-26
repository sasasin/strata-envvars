# `STRATA_SLOT_COPY_DIRECT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

バッチ slot への admission と slot からの通常 resume で、実行状態と QSA K/V をホスト側の checkpoint/KV image 経由で複製する代わりに、GPU 上の session 間で直接コピーするかを選びます。対象は `generate.cpp` の CUDA/HIP バッチ経路です。値が有効でも生成計算そのものを変更するフラグではなく、コピー経路を切り替えます。Metal は専用の `window_slot_copy_main` に分岐するため、このフラグを判定しません（`engine/src/program/generate.cpp:16864-16872`, `16904-16916`, `16958-16980`）。

## 値と判定

`std::getenv` の結果を関数内 `static const bool` に一度保存します。環境変数が存在し、値の先頭文字が NUL でも `'0'` でもない場合に有効です。文字列全体の比較や数値変換はしません（`engine/src/program/generate.cpp:16869-16872`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA/HIP のバッチ経路（既定値注入後の値） | host image 経由。ただし後述の構成では engine が先に `1` を設定 | `1`, `true`, `yes`, `2`, ` 1` など、先頭が `0` 以外の非空文字列 | 空文字、`0`, `0anything` など、先頭が `0` の文字列 |

大文字小文字、空白、数値としての妥当性は検査しません。先頭が空白なら有効で、`false` も先頭が `f` のため有効です。未設定と空文字はどちらも直接コピーを無効にします。

## 有効になる条件

- `--batch` により slot が使われ、slot に状態を移す admission、または slot 状態からの通常 resume が発生すること。単一 request で slot copy がない場合、この選択によるコピーはありません（`engine/src/program/generate.cpp:16802-16803`, `16904-16916`, `16958-16980`）。
- CUDA/HIP 経路であること。Metal は `STRATA_GPU_METAL` の分岐で専用コピー関数を呼び、`slot_copy_direct` を参照しません（`engine/src/program/generate.cpp:16904-16910`, `16958-16966`）。
- 通常の slot resume はこの変数だけで直接コピーに切り替わります。一方、turn checkpoint (`at != nullptr`) からの resume で K/V も直接コピーするには、別途 `STRATA_SLOT_CKPT_KV_DIRECT` も有効である必要があります。それが無効なら checkpoint/KV image の経路を使います（`engine/src/program/generate.cpp:16967-16976`, `16977-17017`）。
- `STRATA_SLOT_COPY_BATCHSYNC` は直接コピー経路に入った後の同期方法を選びます。直接コピーを有効にする条件ではありません（`engine/src/program/generate.cpp:16886-16899`, `engine/src/program/generate.cpp:573-582`）。
- エンジンは一部構成で未設定時に値 `1` をプロセス環境へ設定します。Linux CUDA では `o.batch >= 2` の場合に parallel stack の既定値として適用されます（`engine/src/core/arch_defaults.cpp:226-260`; 呼び出しは `engine/src/program/generate.cpp:4410-4414`）。HIP では `apply_arch_defaults` が、非 integrated の discrete RDNA3 (`gfx1100/1101/1102`) で 2 slot 以上、または Windows の `gfx1151` で 2 slot 以上の場合に parallel stack の一部として設定します。前者は `STRATA_GFX11_DEFAULTS=0`、後者は `STRATA_GFX1151_DEFAULTS=0` で既定値群を止められます。ユーザーがこの変数を明示していれば値は保持されます（`engine/include/strata/core/gfx11_extra.hpp:112-137`, `engine/src/core/arch_defaults.cpp:240-260`, `312-358`, `423-442`）。
- その他の OS/GPU 構成では、上記の既定値注入がないため、環境値が未設定なら host image 経由です。コマンドライン引数からこの変数を設定する処理は確認できません。

## 実行時の詳細

読み取り値は `slot_copy_direct` の関数内 static に保持され、最初に初期化された後の環境変更は反映されません。アーキテクチャ既定値の適用はバッチ処理で switch を読む前に行われます。既定値注入は既存環境変数があれば上書きしないため、明示した空文字や `0` も既定値 `1` に置き換わりません（`engine/src/program/generate.cpp:4287-4321`, `4410-4414`; `engine/src/core/arch_defaults.cpp:253-260`, `302-310`）。

直接経路は各 device について同期し、各 stage の running `SessionState` と QSA K/V state を対応する slot session に（または resume 時に逆方向へ）コピーします。`conversation_checkpoint_copy` と `conversation_kv_copy` に渡す `queued` 引数は `STRATA_SLOT_COPY_BATCHSYNC` の値です。直接経路でなければ checkpoint と K/V を host image に保存して復元します（`engine/src/program/generate.cpp:16873-16932`, `16958-17017`）。

通常 admission と BYIELD の slot 退避が直接コピーの書き込み側を呼びます（`engine/src/program/generate.cpp:20975-21005`, `23586-23596`）。slot resume の直接コピーに失敗すると stderr に `strata batch: restoring slot %d failed (%s); reading the prompt` を出し、その slot からの復元をやめて prompt を先頭から読み直します（`engine/src/program/generate.cpp:19863-19876`）。Admission 側の失敗は `strata serve: batch admission failed: %s` を stderr に出し、slot を uncached 扱いにして `cont` を false にします（`engine/src/program/generate.cpp:23586-23596`）。直接コピー関数の device 同期失敗理由は `batch slot copy: device sync failed` です（`engine/src/program/generate.cpp:16875-16902`）。

## ログと測定値

この変数単独の有効・無効を知らせるログはありません。既定値注入時は構成に応じた parallel-request switches の一覧ログが出る場合がありますが、これは複数スイッチをまとめた既定値ログです（`engine/src/core/arch_defaults.cpp:253-260`, `346-356`, `433-442`）。失敗時の観測可能な経路は上記の admission エラーと resume の prompt 再読ログです。測定値はこの変数単独の条件付き測定として記載できるソース根拠を確認できません。

## 根拠

- 直接読み取りと値判定、cache: `engine/src/program/generate.cpp:16869-16872`
- 直接コピーと host image fallback: `engine/src/program/generate.cpp:16873-16932`, `16958-17017`
- Metal 分岐: `engine/src/program/generate.cpp:16904-16910`, `16958-16966`
- batch default の条件と適用: `engine/src/core/arch_defaults.cpp:226-260`, `312-358`, `423-442`; `engine/src/program/generate.cpp:4287-4321`, `4410-4414`
- 呼び出し元と失敗時の処理: `engine/src/program/generate.cpp:19863-19876`, `20975-21005`, `23586-23596`
