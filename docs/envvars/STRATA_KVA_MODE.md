# `STRATA_KVA_MODE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

KVA が近似対象の後段 layer に渡す残差入力のモードを選びます。`oracle` は `STRATA_KVA_ORACLE` の capture ファイルから layer ごとの残差入力を読み、現在の入力を置き換えます。`identity` はこの置換を行わず、KVA の既定経路を使います。`linear` は enum とログ名を選びますが、この commit には projector による入力置換処理がなく、実際の計算は identity と同じ経路です。

## 値と判定

`include/strata/prefill/kva.hpp` は変数が設定され、空文字でない場合だけ値を検査し、`std::string` の完全一致で分岐します。大文字小文字変換や空白除去、数値変換はありません。

| 値 | 判定結果 | 実際の扱い |
|---|---|---|
| 未設定または空文字 | 代入を行わない | 既定の `identity`。ただし先に `STRATA_KVA_ORACLE` または `STRATA_KVA_PROJECTOR` が設定されていれば、その値による mode が残る |
| `identity` | Identity | oracle による入力置換をしない |
| `oracle` | Oracle | `STRATA_KVA_ORACLE` のファイルを使う oracle 経路を選ぶ |
| `linear` | Linear | ログには `linear` と出るが、現行実装では線形 projector は適用されない |
| 上記以外の非空文字列 | Identity | 既定の identity に戻す。無効値エラーや警告はない |

値は大文字小文字を区別します。たとえば `Oracle`、` oracle`、`linear ` は未知値として Identity になります。

mode の初期値は Identity です。読み取り順は `STRATA_KVA_ORACLE`、`STRATA_KVA_PROJECTOR`、`STRATA_KVA_MODE` なので、非空の `STRATA_KVA_MODE` は前の二つが選んだ mode を上書きします。`STRATA_KVA_MODE=oracle` だけでは oracle ディレクトリは設定されません。Oracle ファイルの場所は別変数 `STRATA_KVA_ORACLE` から取り、fp32/bf16 の形式は `STRATA_KVA_ORACLE_FP32` で決まります。CLI 引数による mode の上書きはこの設定経路にはありません。

根拠: `include/strata/prefill/kva.hpp:69-93,163-181`。

## 有効になる条件

`STRATA_KVA_MODE` は KVA の実行モードに関する設定であり、単独では近似読み取りを有効にしません。KVA 自体が有効で、対象 read が `decline()` の条件を通ったときにだけ `mode` が処理に使われます。ソース上の条件には、KVA 対応 backend、プロセス全体を止める engine 条件がないこと、cold read（`pos0 == 0`）、layer split でないこと、画像や DFlash2 taps がないこと、最小 prompt 長と exact suffix を超える長さが含まれます。既定では未計測の model shape も対象外です。生成側では batch slots、layer split、peer device が process-wide の block 理由になります。

KVA state-only path の backend 定数は Metal で false、それ以外のこの CUDA/HIP 用 header では true です。SYCL engine にはこの prefill 経路がありません。mode は KVA の `on` 判定とは独立で、KVA が off なら mode を設定しても prompt path は変わりません。KVA は `STRATA_KVA` で別途有効にする必要があります。

根拠: `include/strata/prefill/kva.hpp:43-49,98-133`; `src/program/generate.cpp:6257-6278`; `src/prefill/prefill.cpp:2947-2966`。

## 実行時の詳細

設定は `kva_config()` が初めて呼ばれた時に `static const KvaConfig` として一度だけ読み込まれます。通常の実行では生成側の起動時チェックと prefill が同じ設定を参照するため、プロセス起動後に環境変数を書き換えても反映されません。`kva_config_from_env()` 自体は都度環境を読む関数ですが、実行側の `kva_config()` はその結果を cache します。

`oracle` のとき、近似読み取りが成立すれば Prefill は oracle tap を初期化し、近似 layer に入る直前の残差 `R` を `STRATA_KVA_ORACLE` の `L<layer>.bin` から読み込んで置換します。mode が Identity または Linear ならこの oracle 置換は行いません。Linear 用の projector 読み込み・計算もこの commit にはありません。

設定自体に専用ログや無効値警告はありません。近似が適用されたときの KVA 行は `mode identity`、`mode oracle` または `mode linear` を表示します（`STRATA_KVA_SKIP=moe` の場合は表示 mode が `moe-skip` になります）。`oracle` を選んでも必要な `L<layer>.bin` を開けない、seek できない、レコードが不足する、device への upload が失敗する場合、prefill は `kva oracle: ...` のエラーを設定して失敗します。通常の CLI 生成経路では `strata generate: <error>` を stderr に出し、終了コード 1 になります。`STRATA_KVA_ORACLE` が空または未設定なら mode だけではファイル場所が得られず、oracle の読み取り時に空ディレクトリを基準にファイルを開こうとします。

根拠: `include/strata/prefill/kva.hpp:149-195`; `src/prefill/prefill.cpp:2947-2974,2825-2850,2889-2931,3619-3629,3689-3695,5820-5831,7271-7279`; `src/program/generate.cpp:17794-17797`。

## 根拠

- 候補名のリポジトリ全体検索では、実際の読み取りは `include/strata/prefill/kva.hpp:177-181` の直接 `std::getenv` 呼び出し一箇所です。helper 経由の動的な名前渡しはありません。`docs/KVA.md:118` は候補値と linear 未実装の説明、`src/prefill/kva_test.cpp:34` はテスト用環境変数名の一覧であり、実装根拠にはしていません。
- `src/prefill/prefill.cpp:3621-3629` では `kva_subst` が Oracle mode の場合だけ true になり、`:3692-3694` が残差置換を実行します。これにより Linear mode がログ上の選択にとどまることを確認できます。
- Oracle のファイル open/read/seek/upload の失敗文字列と経路は `src/prefill/prefill.cpp:2889-2931` にあります。
- 調査開始時の Strata 作業ツリーは `## main...origin/main` で、`git status --short --branch` 上の未コミット変更はありません。
