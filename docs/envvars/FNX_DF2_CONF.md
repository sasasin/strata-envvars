# `FNX_DF2_CONF`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

split engine の DFlash2 speculative decoding で、DFlash2 が提案した draft token の確率積に対する下限を指定する。積がこの値を下回る draft 位置で chain を打ち切る。未設定時は `0.35`。単一 Session と batch decoder の両方に読み取り箇所がある（`engine/src/split/src/session.cpp:453-456`, `engine/src/split/src/batch.cpp:487-493`）。

この値が変えるのは後続 window で検証する draft の数であり、DFlash2 の候補そのものやモデルの logits を設定するものではない。単一 Session では候補列を `df2_conf` で切り、batch では同じ比較を `conf` で行う（`engine/src/split/src/session.cpp:570-592`, `engine/src/split/src/batch.cpp:526-537`）。候補は通常の window verification に渡され、greedy と sampling で検証・採用を決める（`engine/src/split/src/session.cpp:467-520`）。

## 値と判定

`env_num` が `std::getenv` で値の有無を確認し、有限の十進数として文字列全体を変換する。unset の場合だけ既定値を使う。空文字は設定値として扱われ、変換に失敗する（`engine/src/split/src/env.hpp:24-30,42-49`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| 単一 Session / batch の共通 parser | `0.35` | `0.35`, `0`, `1`, `-0.2`, `1.2`, `1e-3` | 空文字、`true`, `0anything`, ` 0.35`, `0.35 `, `nan`, `inf`, `0x1p-1`, `1e999` |

先頭文字は符号・数字・`.` のいずれかでなければならず、`x` / `X` を含む文字列も拒否する。`strtod` の後ろに文字が残る値、変換不能値、範囲外、非有限値は受け付けない。数値として通れば値域の検査や clamp はなく、負数や `1` より大きい値も受け付ける（`engine/src/split/src/env.hpp:24-30,42-48`）。

chain は累積積 `cum` が設定値より**小さくなった位置**で切られるため、等しい値はその位置を残す。各確率の積は最大 `min(K, df2::kDrafts)` 個まで調べられ、さらに context の空きで制限される（`engine/src/split/src/session.cpp:581-592`, `engine/src/split/src/batch.cpp:526-537`, `engine/src/split/src/batch.cpp:276-278`）。したがって `0` 以下では積が下回らず上限まで残り、`1` より大きければ最初の比較で切られる。`1` では累積積が厳密に `1` の間だけ続く。

CLI 引数や別の環境変数からこの値を上書きする読み取りは見つからない。`session.cpp` のコメントは main engine の `--draft-conf` と同様の役割だと説明するが、sFNX のこの値自体は `env_num("FNX_DF2_CONF", ...)` のみから取得される（`engine/src/split/src/session.cpp:453-456`）。

## 有効になる条件

- 環境変数の parse 自体には OS 分岐がない。適用先は CUDA/HIP 用に構成される sFNX split target で、DFlash2 の有無は `strata_kernels` / `strata_core` から作る library と `FNX_DF2` build define で決まる（`engine/src/split/CMakeLists.txt:80-91,104-114,121-149`）。
- DFlash2 が engine に attach されていること。sFNX は `--draft dflash2`（または `FNX_DRAFT=dflash2`）を選んだ場合に pack を読み込み、engine に DFlash2 を attach する（`engine/src/split/tools/sfnx.cpp:67,108-113,1123-1133`）。
- split target に DFlash2 が組み込まれていること。build は `strata_kernels` と `strata_core` がある場合に `strata_split_df2` を作成し、`FNX_DF2=1` を付けて link する（`engine/src/split/CMakeLists.txt:104-114,121-149`）。未組み込み時の attach は `this engine was built without DFlash2` で失敗する（`engine/src/split/src/engine.cu:1246-1249`）。
- speculative drafts が実行されること。単一 Session では `FNX_SPECULATE=0` なら DFlash2 draft を呼ばず、draft を空にして次の window へ進む（`engine/src/split/src/session.cpp:565-572`）。
- lookup が先に draft 列を提供した場合、その列が DFlash2 confidence 判定より優先される。単一 Session は DFlash2 の先頭候補から lookup が成立すれば confidence loop を飛ばし、batch も lookup の先頭が DFlash2 の先頭候補と一致すれば lookup drafts を採用して confidence loop を飛ばす（`engine/src/split/src/session.cpp:574-585`, `engine/src/split/src/batch.cpp:521-531`）。
- batch 経路では `mode_ == BatchDrafts::mtp` かつ `e_.df2_on()` の場合に DFlash2 経路へ進み、次 window に進行中の lane があるとき `draft_df2` が呼ばれる（`engine/src/split/src/batch.cpp:262-267,330-332`）。

## 実行時の詳細

- 単一 Session は `Session::generate` の開始時に `FNX_DF2_CONF` を通常のローカル変数として読み直す。DFlash2 が attach されていない場合もこの読み取り自体は実行されるため、無効な値は DFlash2 を使わない実行でも例外になる（`engine/src/split/src/session.cpp:398-410,453-457`）。
- batch decoder は `draft_df2` 内の関数 `static const` として値を読む。最初にこの関数へ入った時点の値をプロセス内で cache し、以後の batch window では読み直さない（`engine/src/split/src/batch.cpp:489-493`）。
- CLI 引数による優先順位はない。同一プロセス内で環境値が変更された場合、単一 Session は次の `generate` 呼び出し時に再評価する一方、batch は最初の `draft_df2` 呼び出し後に反映しない。
- 値は確率積の打ち切り判定にだけ使われる。DFlash2 候補は最大 `K`・DFlash2 の draft 上限・context room の範囲で準備され、各候補の積が閾値未満になれば以降を window に加えない（`engine/src/split/src/session.cpp:581-592`, `engine/src/split/src/batch.cpp:276-278,526-537`）。

## ログと測定値

有効な値を読んだことや chain が閾値で切られたことを個別に出力するログは、この変数の読み取り・判定箇所にはない。parser が拒否した場合は `FNX_DF2_CONF: '<値>' is not a number` という例外になる（`engine/src/split/src/env.hpp:42-48`）。単一 Session の例外は sFNX の上位例外 handler に伝わり、`ERR <例外文>` と stderr の `sfnx: failed: <例外文>` を出して終了コード 1 で終了する（`engine/src/split/tools/sfnx.cpp:1097-1102,1160-1166`）。batch の decode で生じた例外も同じ server-level handler に伝わる（`engine/src/split/tools/sfnx.cpp:1160-1166`）。

## 根拠

- parser と変換規則: `engine/src/split/src/env.hpp:24-49`
- 単一 Session の読み取りと判定: `engine/src/split/src/session.cpp:398-410,453-457,565-592`
- batch の適用条件・cache・判定: `engine/src/split/src/batch.cpp:262-267,276-278,330-332,487-537`
- DFlash2 選択と build 条件: `engine/src/split/tools/sfnx.cpp:108-113,1123-1133`; `engine/src/split/CMakeLists.txt:104-149`
- 失敗の通知: `engine/src/split/tools/sfnx.cpp:1097-1102,1160-1166`
