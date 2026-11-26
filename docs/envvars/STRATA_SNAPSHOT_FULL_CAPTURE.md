# `STRATA_SNAPSHOT_FULL_CAPTURE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`--serve` の会話キャッシュから復元した K/V を、次の park で再利用するために保持する処理を止める診断用スイッチです。設定されていると、park 時に前回の K/V バッファを `ConversationKvReuse` として引き継がず、保存処理は再利用可能な prefix を 0 token として扱います。そのため、次の snapshot では K/V を再取得します。さらに CUDA 側で条件が合う場合の host K/V block exchange も無効にします。通常の会話 cache の有効化自体や、park / restore の可否を切り替えるスイッチではありません。同梱の比較ツール `terminal/tools/conversation_cache_growth.py` は `--run` 時に full arm の子プロセスへ `1` を設定し、incremental arm では削除します（`terminal/tools/conversation_cache_growth.py:64-78,98-113`）。エンジン側の実装根拠は `engine/src/program/generate.cpp:20036-20040`, `engine/sycl/src/program/generate.cpp:11022-11026`, `engine/src/core/conversation_state.cpp:787-790`, `engine/src/core/conversation_state.cpp:603-605,641-645`）。

## 値と判定

両方の復元経路と snapshot 交換準備は `std::getenv(...) != nullptr` 相当の有無判定です。文字列の比較や数値変換はありません。未設定だけが無効で、空文字を含む任意の設定値が有効です（`engine/src/program/generate.cpp:20036`, `engine/sycl/src/program/generate.cpp:11022`, `engine/src/core/conversation_state.cpp:789`）。

| 条件 | unset | 設定ありで有効 | 設定ありで無効 |
|---|---|---|---|
| CUDA/HIP の `engine/src/program` 復元経路 | K/V retention を通常どおり試みる | `1`, `0`, `true`, `false`, `0anything`, 空文字などすべて | なし |
| SYCL の `engine/sycl/src/program` 復元経路 | K/V retention を通常どおり試みる | `1`, `0`, `true`, `false`, `0anything`, 空文字などすべて | なし |
| CUDA 側 snapshot block exchange 準備 | 他の条件を満たせば準備可能 | 上記いずれの値でも準備を拒否 | なし |

大文字小文字、前後の空白、数値としての妥当性は検査されません。CLI 引数や設定ファイルからこの判定を上書きする処理は、該当コードにありません。

## 有効になる条件

- K/V retention の抑止は、`incoming` の会話 snapshot を restore する `--serve` の会話キャッシュ経路で適用されます。会話キャッシュが無効、parked snapshot の restore がない、または通常の新規 prompt 処理だけの場合、この条件分岐は通りません（`engine/src/program/generate.cpp:19988-20046`, `engine/sycl/src/program/generate.cpp:10971-11031`）。
- restore 後の通常の `conversations.retain(...)` 呼び出しを飛ばすため、次の park に対して保持 K/V の再利用がありません。snapshot 保存側は reuse が空なら `unchanged = 0` とし、その prefix を再利用せず K/V を保存します（`engine/src/core/conversation_cache.hpp:332-342`, `engine/src/core/conversation_state.cpp:603-605,641-645`, `engine/src/core/conversation_snapshot.cpp:424-448`; SYCL は `engine/sycl/src/core/conversation_snapshot.cpp:178-203`）。
- CUDA 側の block exchange 抑止は、`conversation_snapshot_swap_prepare` を呼ぶ交換候補の経路に限られます。block サイズ、incoming snapshot、RAM K/V など他の条件で候補にならなければ、この判定による追加の変化はありません（`engine/src/program/generate.cpp:19759-19774`, `engine/src/core/conversation_state.cpp:779-796`）。SYCL の generate 実装にはこの swap prepare 呼び出しが見つからず、該当する効果はありません。
- `STRATA_SNAPSHOT_VERIFY` とは独立した変数です。両方設定するとどちらの有無判定も成立し、MTP の検証分岐は別途実行されます（`engine/src/program/generate.cpp:20009-20021,20036-20040`, `engine/sycl/src/program/generate.cpp:10995-11007,11022-11026`）。

## 実行時の詳細

環境変数は各 restore 後の retention 判定時と、CUDA 側の交換準備時に `getenv` で読み直されます。関数内 `static` cache はなく、起動時に一度読む実装でもありません。該当の読み取り経路が再度通れば、その時点のプロセス環境が判定に使われます（`engine/src/program/generate.cpp:19773-19774,20036`, `engine/sycl/src/program/generate.cpp:11022`）。

通常は restore した `incoming->kv` と stage ごとの K/V を `conversations.retain` に渡し、次回の park が同じ会話の prefix を再利用できるようにします。変数が設定されていればこの移譲を省略します。park 時には reuse が空であるため `unchanged` が 0 になり、K/V save は保持済み prefix をコピー対象から除外しません（`engine/src/core/conversation_cache.hpp:336-342`, `engine/src/core/conversation_state.cpp:603-605,641-645`, `engine/src/core/conversation_snapshot.cpp:424-448`）。CUDA 側の交換最適化は swap prepare が `false` を返すため行われず、通常の restore / park 経路に続きます（`engine/src/core/conversation_state.cpp:787-796`, `engine/src/program/generate.cpp:19988-20040`）。

## ログと測定値

この変数専用の有効・無効ログやエラー文言はありません。通常の restore ログ（例: `strata serve: conversation cache: restored ...`）や park ログが出る経路では引き続き出力されます。CUDA 側の park ログは `reused_kv_bytes=%zu` を含み、SYCL 側の park ログも同じ項目を出力します。値が設定されている場合、この変数が設定された状態で restore された K/V retention からの再利用 byte 数は 0 になります。ただし、実行中に変数を切り替えた場合や別の経路での再利用値までは保証しません（`engine/src/program/generate.cpp:20043-20046,14491-14500`, `engine/sycl/src/program/generate.cpp:11028-11031,8490-8498`）。コードおよび参照した資料に、この変数による性能測定値はありません。

同名は `engine/src/core/conversation_snapshot_test.cpp` のテストにも現れますが、本番動作の根拠にはしていません。`terminal/data/settings-register.json`、`docs/DETAILS.md`、測定記録にも名前がありますが、これらは環境から値を読む実装ではありません。

## 根拠

- `engine/src/program/generate.cpp:19755-19835,19988-20046` — CUDA/HIP 側の交換候補、restore、retention 抑止。
- `engine/sycl/src/program/generate.cpp:10971-11031` — SYCL の restore と retention 抑止。
- `engine/src/core/conversation_state.cpp:603-605,641-645,779-796` — 保存時の reuse prefix と swap prepare の有無判定。
- `engine/sycl/src/core/conversation_state.cpp:271-284` — SYCL の保存で reuse prefix を渡す処理。
- `engine/src/core/conversation_snapshot.cpp:418-448`、`engine/sycl/src/core/conversation_snapshot.cpp:172-203` — unchanged prefix と K/V save の処理。
- `engine/include/strata/core/conversation_cache.hpp:332-342` — retention の保存先と容量条件。
- `terminal/tools/conversation_cache_growth.py:64-78,98-113` — 比較ツールが full arm で子プロセス環境へ設定し、incremental arm で削除する処理。

`docs/DETAILS.md:898-904` は `STRATA_SNAPSHOT_FULL_CAPTURE=1` と記していますが、現行コードは値 `1` かどうかを見ず、設定の有無で分岐します。したがって `=0`、空文字などもコード上は同じ効果です。
