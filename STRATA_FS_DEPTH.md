# `STRATA_FS_DEPTH`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

Foresight swap が VRAM スロットを再利用するまでに必要な、完了済み verify window 数を指定します。スロット内の expert を直前の計画が参照した後、指定数の window が完了するまでは別 expert のコピー先にしません。値を大きくするとスロットの参照中のデータを保護する期間が長くなり、空きスロットが見つからずコピーが見送られる場合があります。

## 値と判定

| 環境変数の状態 | `depth` |
|---|---:|
| 未設定 | 4 |
| 設定あり | `atoi` で変換した整数。ただし2未満は2 |
| 空文字、数字で始まらない文字列 | `atoi` の結果0となり、2 |
| 数字の後ろに文字が続く文字列 | 数字部分を変換し、2未満なら2（例: `3abc` は3、`1abc` は2） |
| 負値、0、1 | 2 |

文字列全体の妥当性検査や上限 clamp はありません。`atoi` の整数型で表現できない入力の結果は C/C++ の `atoi` の範囲外入力に依存し、ソースから有効な値として保証できません。

## 有効になる条件

この実装は CUDA の serve/decode 経路にあります。`STRATA_FS_DEPTH` 自体は `STRATA_FS_SLOTS` が `atoi` で正数になり、Foresight swap 初期化に進んだ場合に読み取られます。`STRATA_FS_SLOTS` が未設定、0以下、または数値に変換できない値なら swap は作られず、この変数の値は読みません。

`STRATA_VERIFY_DEVICE_PLAN` が設定され、かつ `atoi` の結果が0以外の場合は Foresight swap を無効にして返るため、`STRATA_FS_DEPTH` は読み取られません。その場合 stderr に `strata serve: foresight swap: off beside STRATA_VERIFY_DEVICE_PLAN (the device would plan resident layers without the host)` を出します。初期化で VRAM 確保などに失敗した場合も swap は無効になり、depth は実際のスロット再利用に使われません。

## 実行時の詳細

`foresight_swap_from_env()` が swap オブジェクトの作成時に環境を読み、`depth` に保存します。起動時に一度だけ読む静的キャッシュではありませんが、既存オブジェクトの動作中に環境を書き換えても保存済みの値は変わりません。新しい swap オブジェクトが作られれば、その作成時の環境値が読み直されます。

コピー要求の元データ `ExpertSource` が対象 expert の pinned 領域を持つことも必要です。pinned でなければ miss/prediction からコピーを登録しません。expert を swap slot から GPU で使う際、`take()` はその slot の `last_ref` を現在の完了済み window 数に更新します。後続の miss/prediction により slot を再利用する際は、`last_ref + depth <= completed` を満たす slot だけを候補にします。満たさない場合、その slot はまだ再利用しません。swap 処理は層ごとの slot から最も古く参照された再利用可能な slot を選び、候補がなければ `busy` を増やしてコピー要求を見送ります。verify window の完了数は serve の decode loop が各 window の確定後に増やします。

初期化に成功すると stderr に `reuse after %d windows` を含む `strata serve: foresight swap: ...` 行を出します。この `%d` が clamp 後の depth です。要求元に返す専門家がまだコピー完了していなければ、その window では swap slot を使えず、従来の miss 経路に進みます。

## 根拠

- `src/core/expert_source.cpp:4951-4966`: `STRATA_FS_SLOTS` による swap 有効判定、`STRATA_VERIFY_DEVICE_PLAN` の除外、各値の読み取り、`STRATA_FS_DEPTH` の既定値4・下限2。
- `src/core/expert_source.cpp:4973-4975`: 初期化成功時に適用 depth を含む stderr ログ。
- `src/core/expert_source.cpp:4839-4873`: swap slot の hit 判定と `last_ref` 更新。
- `src/core/expert_source.cpp:4887-4936`: pinned source の確認、slot 再利用候補を `last_ref + depth <= now` で選ぶ処理、候補がない場合の扱い。
- `src/program/generate.cpp:8182-8193`: serve 実行経路で swap を作成し dispatch / look-ahead に接続。
- `src/program/generate.cpp:11659-11666,11954-11967`: verify window 確定後に完了数を増加。
- `include/strata/core/foresight_swap.hpp:2-14,49`: Foresight swap の役割、depth の既定4と安全期間の説明、構造体の初期値。
- `docs/DETAILS.md:1680-1687`: `STRATA_FS_SLOTS` の機能と測定値を記載。ただし `STRATA_FS_DEPTH` の値別挙動や性能値は説明していません。性能比較はこの変数の効果として扱っていません。
