# `STRATA_I8_DEFER`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

CUDA/HIP prefill の streamed walk で、int8 expert group が開いている間に routing が選ばなかった expert entry に到達したとき、その entry の処理を理由に開いた group を早期実行するかを制御する。`STRATA_I8_DEFER=1` のときは、リング容量に余裕がある間、開いた int8 group が実行されるまで entry の slot を stager に返さない。int8 group が有効でない経路や、通常の staged walk には影響しない（`engine/src/prefill/prefill.cpp:7534-7558`）。

## 値と判定

`run_impl` 内の streamed walk で初めて評価される関数内 `static const bool` が `std::getenv` の結果を読み、未設定でなく先頭文字が `'1'` なら有効にする。文字列全体の parse、空白除去、大文字小文字変換はない（`engine/src/prefill/prefill.cpp:4214-4215,7534-7548`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA/HIP streamed walk の最初の評価 | 無効 | `1`, `10`, `1anything` | 空文字、`0`, `true`, `false`, `-1`, ` 1` |

2 文字目以降は無視されるため、`1anything` も有効になる。一方、先頭文字が `1` でなければ、数値としての妥当性にかかわらず無効。別の既定値や CLI 上書きはない。評価結果は `static` に保持され、最初の評価後にプロセス環境を変更しても反映されない（同上）。

## 有効になる条件

- CUDA/HIP の `Prefill::run_impl` の streamed walk に入り、対象 entry がその層の routing に選ばれていないこと（`engine/src/prefill/prefill.cpp:4214,7534-7564`）。
- その層が int8 expert group (`i8_l`) を使い、開いた group に streamed ring slot が少なくとも 1 つあること（`engine/src/prefill/prefill.cpp:6351-6378,7001-7012,7229-7235,7551-7553`）。int8 の層判定はデバイス・layout と重み形式、実行条件に依存し、クラス既定または `STRATA_EXPERT_I8=1` による選択を含む（同ファイル `:2193-2207,6370-6409`）。
- `STRATA_PREFILL_GROUP_GATHER` が無効だと `i8_l` の成立条件を満たさず、この制御対象の int8 group 経路には入らない。同変数は未設定なら有効、設定値は `atoi` で変換して 0 以外が有効（同ファイル `:6359-6362`）。
- リングに十分な空きがあること。コードは `(k + 1 - given_upto) + kGroupMax + 2 < m.ring` の場合だけ defer する。等号になる場合を含め、条件を満たさなければ開いた group を先に flush する（同ファイル `:4941-4946,7551-7558`）。
- 有効条件は実行経路・層ごとに評価される。通常の非-streamed staged walk はこの分岐を通らない。コードに OS 固有条件はない（同ファイル `:7496-7505,7534-7558`）。

## 実行時の詳細

`release_to` は、routing が選ばなかった entry を順に処理する。有効条件を満たす場合、まず entry 自身の slot に compute stream 上の使用済み event を記録し、`consumed` を進めるが、`give_back(consumed)` は呼ばない。そのため stager はその entry を再利用できず、開いた int8 group の slot も読み取り完了まで保持される。条件を満たさない場合は、開いた group を `flush(0)` してからその entry を stager に返す（`engine/src/prefill/prefill.cpp:7551-7559`）。

routing が選んだ expert は `compute` に渡されて group に加わる。group が完了して flush されると、flush は最後の copy を待ち、int8 group を実行し、group の ring slot を解放する。`gg_nslots` が 0 になった後の walk が保留中の entry を stager に返す（同ファイル `:7120-7153,7229-7235,7561-7585`）。リングに空きが少なくなった場合は前述の境界条件により早期 flush に戻るため、entry の返却を無制限に遅らせない。

## ログと測定値

この環境変数の値や defer の選択を知らせる専用ログはない。int8 group の record 作成に失敗した場合は `prefill: int8 experts: the group's record could not be made (%lld rows, %d experts)\n` を stderr に出して `exit(1)` する。routing が選んだ expert のデータが resident・streamed・peer のいずれにもない場合は `err` に `prefill: an expert is neither resident, streamed nor on the peer` を設定して失敗を返す（`engine/src/prefill/prefill.cpp:7142-7145,7576-7581`）。

## 根拠

- `engine/src/prefill/prefill.cpp:4214-4219` — `run_impl` の位置。
- `engine/src/prefill/prefill.cpp:6351-6378,6380-6409,7001-7012` — int8 group と grouped streamed path の適用条件。
- `engine/src/prefill/prefill.cpp:4941-4946,7120-7153,7229-7235,7534-7585` — ring slot の返却、defer 判定、flush と失敗経路。
- `docs/SETTINGS.md:116` — Strata の設定一覧は NVIDIA/AMD 向けの on/off 候補として掲載。値の細則はソースに基づく。
