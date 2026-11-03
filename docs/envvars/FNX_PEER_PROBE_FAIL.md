# `FNX_PEER_PROBE_FAIL`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Strata 同梱の `strata-split` HIP engine が peer push を使うか起動時に判定するとき、peer probe を実行せず失敗扱いにする診断用フックです。`FNX_PEER_PROBE_FAIL=1` なら peer push は選ばれず、その実行全体で host-memory exchange に切り替わります。通常の利用設定というより fallback 経路を選ぶテスト・診断用です。

## 値と判定

この変数は整数として parse せず、環境から得た文字列全体を `"1"` と `strcmp` で比較します。

| 値 | 判定 | 結果 |
|---|---|---|
| 未設定 | 強制失敗ではない | 通常の peer probe を呼ぶ |
| `1` | 強制失敗 | probe を呼ばず、理由を `forced failure (FNX_PEER_PROBE_FAIL=1)` として peer push を不採用にする |
| 空文字、`0`、`01`、`1 `、`true` など | 強制失敗ではない | 通常の peer probe を呼ぶ |

大文字小文字・空白の正規化、数値変換、範囲検査はありません。値がちょうど `1` の場合だけ一致します。なお、peer push を試みない判断になった場合は helper が先に戻るため、この変数の値は読まれず、ログも出ません。

## 有効になる条件

- `FNX_HIP` が有効な HIP ビルドで `fnx::Engine` が構築されること。engine の peer policy 呼び出しは `#if FNX_HIP` 内にあります。CUDA ビルドではこの呼び出しがなく、この変数は Strata に読まれません。
- peer policy が peer push を試す判断であること。`FNX_PEER=0` は即時に host exchange を選ぶため、この変数による forced-failure 判定には進みません。`FNX_PEER` が未設定なら、この commit の `PEER_DEFAULT_ON` は `true` です。`FNX_PEER` が設定されていて値がちょうど `0` 以外なら試行します。
- peer push を試すときでも、この変数が `1` 以外なら通常の probe が実行されます。probe 自体が失敗した場合も host exchange へ fallback します。

この変数は CLI 引数や別の環境変数で `1` が上書きされるものではありません。ただし `FNX_PEER=0` は上記の通り先に policy を終了させます。engine の構築時に一度 decision が `peer_on` に保存され、実行中に環境を変更しても判定し直しません。

## 実行時の詳細

HIP の `Engine` constructor は搭載 card の device ID 一覧を作り、`peer_decide()` を呼びます。policy が peer push を試す場合に限って helper がこの環境変数を取得します。値が `1` なら probe callback を実行せず、`PeerDecision.use` は false のまま、理由付きの1行を返します。engine は非空の decision line を stderr に `fnx: ` を付けて出力し、`peer_on` を false に設定します。

その後、`peer_on` が false なので peer 用 mailbox は割り当てられず、attention merge buffer は host exchange 用の buffer になります。peer push を有効にする probe（peer access の有効化を含む）は呼ばれません。変数そのものによる終了や例外はなく、engine は host exchange で続行します。実際にモデル実行できるかはこの変数だけでは決まりません。

観測される行は次のとおりです（stderr）。

```text
fnx: The cards cannot push into each other's memory here (forced failure (FNX_PEER_PROBE_FAIL=1)): using the host exchange for this run.
```

`FNX_PEER=0` など peer push を試さない経路では、この fallback 理由行は出ません。probe 成功時の peer push 有効ログも出ません。

## 根拠

- `src/split/src/hip/peer_policy.hpp:26-40` — `FNX_PEER` の判定順、`FNX_PEER_PROBE_FAIL` の完全一致判定、probe callback を省略する forced-failure 分岐、fallback line と `use` の値。
- `src/split/src/hip/peer_policy.hpp:17-18` — unset 時に使う peer policy default が `true`。
- `src/split/src/engine.cu:23-26,81-105` — HIP build guard、Engine constructor 内の policy 呼び出し、stderr 出力、decision の保存と peer push 成功ログ。
- `src/split/src/engine.cu:245-249` — `peer_on` のときだけ peer mailbox を確保し、そうでないとき host buffer を使う。
- `src/split/src/hip/peer.h:58-80` — 通常 probe callback が行う peer access 可否確認と peer access 有効化。forced failure 時にはこの callback が呼ばれない。
- `src/split/tools/peer_policy_test.cpp:42-51` — 同梱 CPU-only policy test が `1` で callback を呼ばず fallback decision となるケースを記述。ただし本書の実装挙動の根拠は本番コードを優先。
