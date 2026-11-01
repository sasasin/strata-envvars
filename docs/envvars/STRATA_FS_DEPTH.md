# `STRATA_FS_DEPTH`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Foresight swap space の VRAM slot を再利用するまでに必要な、完了済み decode window 数を指定します。slot を参照した window がまだ読み終えていない間に、その slot の内容を別 expert で上書きしないための猶予です。Foresight swap space 自体は `STRATA_FS_SLOTS` で opt-in する CUDA の serve 経路です。`STRATA_FS_DEPTH` 単独では機能を有効にしません。

## 値と判定

`foresight_swap_from_env()` 内の共通 `env_int` lambda が `std::getenv(name)` で読み、設定値は `std::atoi` に渡します。変換後の値が下限より小さい場合は下限へ引き上げます（`src/core/expert_source.cpp:6547-6552`）。

| 環境変数の状態・値 | `f->depth` |
| --- | ---:|
| 未設定 | 4（既定値） |
| 空文字、数値に変換できない文字列 | 2（`atoi` が 0 を返し、下限で clamp） |
| `atoi` の結果が 2 未満（負値、0、1 を含む） | 2 |
| `atoi` の結果が 2 以上 | その整数値 |

全体の厳密な数値 parse や上限 clamp はありません。`atoi` のため先頭の空白と符号は変換対象になり、数値の後ろに文字があっても数値部分が使われます（例: `5x` は 5、`x5` は変換結果 0 となり 2）。整数としての範囲外入力に対する明示的な検査もありません。

## 有効になる条件

- `STRATA_FS_SLOTS` が設定され、`atoi` の結果が 1 以上であること。未設定・空文字・非数値・0・負値では swap pool を作らず、その時点で `STRATA_FS_DEPTH` も読みません（`src/core/expert_source.cpp:6537-6542`）。
- `STRATA_VERIFY_DEVICE_PLAN` が未設定または `atoi` の結果 0 であること。非 0 なら pool の作成を拒否し、stderr に `strata serve: foresight swap: off beside STRATA_VERIFY_DEVICE_PLAN (the device would plan resident layers without the host)` と出します（同:6542-6545）。
- Foresight swap の初期化が成功すること。slot の CUDA allocation または event 作成に失敗すると初期化失敗となり、caller は pool を破棄します（同:6302-6356, 6554-6557）。
- 実際にコピー要求が通るには、source と expert のデータがあり、source がその expert を pinned と判定する必要があります。条件を満たさない miss/prediction は slot コピーを要求せず、通常の経路のままです（同:6472-6488）。

CLI 引数や他の環境変数から depth を上書きする処理は見つかりません。`STRATA_FS_AHEAD` や `STRATA_LOOKAHEAD` は予測経路の有無に関係しますが、depth の parse 値は変更しません（`src/program/generate.cpp:7734-7742`）。

## 実行時の詳細

serve の生成処理が Foresight swap pool を作るときに環境から読み、pool の `depth` フィールドへ保持します。`static` cache ではなく、その pool の初期化ごとの読み取りです。pool 作成呼び出しは `src/program/generate.cpp:11108-11121` にあります。成功時の stderr 初期化ログは `reuse after %d windows` として採用値を出します（`src/core/expert_source.cpp:6559-6562`）。

各 decode window の完了時に `completed` カウンターを1増やします（`src/program/generate.cpp:16581-16587, 17056-17059`）。slot を再利用候補にする際、実装は `sl.last_ref + depth > now` なら候補から除外します。`now` は完了済み window 数、`last_ref` は slot を最後に plan へ渡した時点の完了数です。従って depth を大きくすると slot の再利用を遅らせ、小さくすると下限2の範囲で早めます。候補 slot がない場合は `busy` カウンターを増やして要求を見送り、depth を満たすまで待機するのではありません（`src/core/expert_source.cpp:6435-6438, 6472-6504`）。コピー未完了 slot は `take()` で未着として扱われ、expert はその時点で swap slot からは提供されません（同:6404-6415）。

実行終了時に `foresight swap: ... no free slot ...` を含む集計行が stderr に出ます（`src/core/expert_source.cpp:6524-6534`; 出力箇所 `src/program/generate.cpp:17177`）。コピーの失敗時は `strata serve: foresight swap: a copy failed - swap space off` が stderr に出て、それ以降の要求コピーを止めます（`src/core/expert_source.cpp:6393-6400, 6472-6474`）。初期化の割当失敗時は理由と `swap space off` が stderr に出ます（同:6325-6332, 6554-6557）。

## 根拠

- 読み取り、既定値、最小値 clamp、起動条件、初期化ログ: `src/core/expert_source.cpp:6537-6562`
- slot の再利用判定と候補不足時の動作: `src/core/expert_source.cpp:6435-6438, 6472-6504`
- Foresight swap の serve 側生成と接続: `src/program/generate.cpp:11108-11129`
- 完了 window カウンター: `src/program/generate.cpp:16581-16587, 17056-17059`
- Foresight swap の opt-in 説明と `STRATA_FS_DEPTH` の既定値に関するコメント: `include/strata/core/foresight_swap.hpp:2-14, 49-53`
- `STRATA_FS_SLOTS` の適用範囲と過去測定: `docs/DETAILS.md:1030, 1437`。これは `STRATA_FS_SLOTS` の資料であり、`STRATA_FS_DEPTH` 単独の性能測定値は記載されていません。
